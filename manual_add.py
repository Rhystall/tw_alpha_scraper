"""
manual_add.py - Manually add Twitter account with pre-obtained cookies.

This script bypasses the login process by directly injecting valid session
cookies obtained from your browser. Useful when VPS IPs are blocked by Cloudflare.

How to get cookies from your browser:
1. Login to Twitter/X in your browser
2. Open DevTools (F12) -> Application -> Cookies -> https://x.com
3. Copy the values of 'auth_token' and 'ct0'
4. Format as: auth_token=xxx; ct0=yyy
"""

import asyncio
from twscrape import API
from loguru import logger


def parse_cookies(cookie_string: str) -> str:
    """
    Parse and validate cookie string.
    Expected format: "auth_token=xxx; ct0=yyy" or just the raw string.
    Returns the cookie string in the format twscrape expects.
    """
    cookies = {}
    
    # Parse cookie string into dict
    for part in cookie_string.split(";"):
        part = part.strip()
        if "=" in part:
            key, value = part.split("=", 1)
            cookies[key.strip()] = value.strip()
    
    # Validate required cookies
    if "auth_token" not in cookies:
        raise ValueError("Cookie string must contain 'auth_token'")
    if "ct0" not in cookies:
        raise ValueError("Cookie string must contain 'ct0'")
    
    logger.info(f"Parsed cookies: auth_token=***{cookies['auth_token'][-6:]}, ct0=***{cookies['ct0'][-6:]}")
    
    # Return as formatted string for twscrape
    return cookie_string.strip()


async def manual_add_account():
    print("\n" + "=" * 50)
    print("   MANUAL ACCOUNT ADDITION (Cookie Injection)")
    print("=" * 50 + "\n")
    
    # Get account credentials
    username = input("Username (without @): ").strip()
    password = input("Password: ").strip()
    email = input("Email: ").strip()
    email_password = input("Email Password: ").strip()
    
    print("\n--- Cookie Input ---")
    print("Format: auth_token=AAA...; ct0=BBB...")
    print("Get these from browser DevTools -> Application -> Cookies -> x.com\n")
    cookie_string = input("Paste Cookie String: ").strip()
    
    # Parse and validate cookies
    try:
        parsed_cookies = parse_cookies(cookie_string)
    except ValueError as e:
        logger.error(f"Invalid cookie format: {e}")
        return
    
    api = API()
    
    # Step 1: Check and delete existing account
    logger.info(f"Checking if account '{username}' already exists...")
    try:
        await api.pool.delete_accounts([username])
        logger.warning(f"Deleted existing account: {username}")
    except Exception:
        logger.debug(f"No existing account found for: {username}")
    
    # Step 2: Add account with cookies
    logger.info(f"Adding account '{username}' with provided cookies...")
    try:
        await api.pool.add_account(
            username=username,
            password=password,
            email=email,
            email_password=email_password,
            cookies=parsed_cookies
        )
        logger.success(f"Successfully added account: {username}")
        logger.info("Account is ready to use. No login required!")
        
        # Verify by checking account status
        accounts = await api.pool.accounts_info()
        for acc in accounts:
            if acc.username == username:
                logger.info(f"Account status - Active: {acc.active}, Logged in: {acc.logged_in}")
                break
                
    except Exception as e:
        logger.error(f"Failed to add account: {e}")
        raise


async def main():
    logger.add("manual_add.log", rotation="10 MB")
    await manual_add_account()


if __name__ == "__main__":
    asyncio.run(main())
