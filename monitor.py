import asyncio
import json
import random
import os
import re

# ============================================================
# MONKEY PATCH FIX for "Failed to parse scripts" error
# See: https://github.com/vladkens/twscrape/issues/287
# This must be applied BEFORE importing twscrape.API
# ============================================================
def script_url(k: str, v: str):
    return f"https://abs.twimg.com/responsive-web/client-web/{k}.{v}.js"

def patched_get_scripts_list(text: str):
    try:
        scripts = text.split('e=>e+"."+')[1].split('[e]+"a.js"')[0]
    except IndexError:
        return
    
    try:
        for k, v in json.loads(scripts).items():
            yield script_url(k, f"{v}a")
    except json.decoder.JSONDecodeError:
        # Fix all unquoted keys - more aggressive pattern
        fixed_scripts = re.sub(
            r'([,\{])(\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*):',
            r'\1\2"\3"\4:',
            scripts
        )
        for k, v in json.loads(fixed_scripts).items():
            yield script_url(k, f"{v}a")

# Apply monkey patch
from twscrape import xclid
xclid.get_scripts_list = patched_get_scripts_list
# ============================================================

from twscrape import API
from discord_webhook import DiscordWebhook, DiscordEmbed
from loguru import logger

# Constants
CONFIG_PATH = "config.json"
STATE_PATH = "state.json"

def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

def load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, "r") as f:
            return json.load(f)
    return {}

def save_state(state):
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=4)

async def send_discord_alert(webhook_url, target_name, followed_user):
    webhook = DiscordWebhook(url=webhook_url)
    
    embed = DiscordEmbed(
        title=f"New Follow by {target_name}",
        description=f"**{followed_user.name}** (@{followed_user.username})",
        color="03b2f8"
    )
    
    embed.add_embed_field(name="Bio", value=followed_user.description or "No bio", inline=False)
    embed.add_embed_field(name="Profile Link", value=f"https://x.com/{followed_user.username}", inline=False)
    embed.set_thumbnail(url=followed_user.profile_image_url)
    embed.set_timestamp()
    
    webhook.add_embed(embed)
    response = webhook.execute()
    return response

async def monitor_target(api, target_id, webhook_url, state):
    try:
        # Get target user info for the alert header
        target_user = await api.user_by_id(int(target_id))
        target_name = target_user.name if target_user else f"ID: {target_id}"
        
        last_seen_id = state.get(str(target_id))
        logger.info(f"Checking follows for {target_name} (Last seen ID: {last_seen_id})")
        
        new_follows = []
        is_first_run = last_seen_id is None
        
        # twscrape.following returns an async generator
        async for user in api.following(int(target_id)):
            if str(user.id) == last_seen_id:
                break
            
            new_follows.append(user)
            
            # Limit initial fetch to avoid massive spam if the account is old
            if is_first_run and len(new_follows) >= 5:
                break
        
        if new_follows:
            logger.info(f"Found {len(new_follows)} new follows for {target_name}")
            
            # Update state with the newest one (first in list)
            state[str(target_id)] = str(new_follows[0].id)
            save_state(state)
            
            if not is_first_run:
                # Send alerts for each new follow (in reverse order to maintain timeline)
                for user in reversed(new_follows):
                    await send_discord_alert(webhook_url, target_name, user)
                    logger.success(f"Alert sent for @{user.username}")
                    await asyncio.sleep(1) # Small delay between webhooks
            else:
                logger.info("First run: State initialized, skipping initial alerts.")
        else:
            logger.debug(f"No new follows for {target_name}")
            
    except Exception as e:
        logger.error(f"Error monitoring {target_id}: {e}")

async def main():
    logger.add("monitor.log", rotation="500 MB")
    config = load_config()
    api = API() # twscrape uses accounts.db by default
    
    webhook_url = config.get("discord_webhook_url")
    poll_interval = config.get("poll_interval", 300)
    targets = config.get("targets", [])
    
    if not targets:
        logger.warning("No targets found in config.json")
        return

    logger.info(f"Starting monitor for {len(targets)} targets. Poll interval: {poll_interval}s")

    while True:
        state = load_state()
        
        for target_id in targets:
            await monitor_target(api, target_id, webhook_url, state)
            # Random jitter between targets
            await asyncio.sleep(random.uniform(5, 15))
            
        logger.info(f"Cycle complete. Sleeping for {poll_interval}s...")
        # Add jitter to the main poll interval too
        jitter = random.uniform(-30, 30)
        await asyncio.sleep(max(10, poll_interval + jitter))

if __name__ == "__main__":
    asyncio.run(main())
