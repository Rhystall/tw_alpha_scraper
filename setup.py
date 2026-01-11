"""
setup.py - Account Management for Twitter Monitor

Manages worker accounts in the twscrape database with proxy support.

Usage:
    python setup.py add     - Add a new worker account with proxy
    python setup.py login   - Login all accounts to generate cookies
"""

import asyncio
import sys
from twscrape import API
from loguru import logger


async def add_account():
    """Add a new worker account with residential proxy support."""
    print("\n" + "=" * 60)
    print("   📝 ADD NEW WORKER ACCOUNT (with Proxy)")
    print("=" * 60 + "\n")
    
    # Get account credentials
    username = input("Twitter Username (without @): ").strip()
    password = input("Twitter Password: ").strip()
    email = input("Email: ").strip()
    email_password = input("Email Password: ").strip()
    
    # Get proxy
    print("\n--- Proxy Configuration ---")
    print("Format: http://user:pass@ip:port")
    print("Example: http://customer-xxx:yyy@proxy.provider.com:12345")
    proxy_string = input("Proxy String: ").strip()
    
    if not proxy_string:
        logger.warning("No proxy provided. Account may be rate-limited on VPS.")
    
    api = API()
    
    # Step 1: Clean slate - delete existing account if any
    logger.info(f"Checking for existing account: {username}")
    try:
        await api.pool.delete_accounts([username])
        logger.warning(f"Deleted existing account: {username}")
    except Exception:
        logger.debug(f"No existing account to delete: {username}")
    
    # Step 2: Add account with proxy
    logger.info(f"Adding account: {username}")
    try:
        if proxy_string:
            await api.pool.add_account(
                username=username,
                password=password,
                email=email,
                email_password=email_password,
                proxy=proxy_string
            )
            logger.success(f"Account '{username}' added with proxy!")
        else:
            await api.pool.add_account(
                username=username,
                password=password,
                email=email,
                email_password=email_password
            )
            logger.success(f"Account '{username}' added (no proxy)!")
        
        print("\n✅ Account added successfully!")
        print("Next step: Run 'python setup.py login' to authenticate.")
        
    except Exception as e:
        logger.error(f"Failed to add account: {e}")
        raise


async def login_accounts():
    """Login all accounts to generate session cookies."""
    print("\n" + "=" * 60)
    print("   🔐 LOGIN ALL ACCOUNTS")
    print("=" * 60 + "\n")
    
    api = API()
    
    logger.info("Starting login process for all accounts...")
    await api.pool.login_all()
    
    logger.info("Login process completed.")
    print("\n✅ Login complete! Check logs for any errors.")
    print("If successful, run 'python monitor.py' to start monitoring.")


async def list_accounts():
    """List all accounts and their status."""
    print("\n" + "=" * 60)
    print("   📋 ACCOUNT STATUS")
    print("=" * 60 + "\n")
    
    api = API()
    accounts = await api.pool.accounts_info()
    
    if not accounts:
        print("No accounts found.")
        return
    
    for acc in accounts:
        if isinstance(acc, dict):
            username = acc.get("username", "Unknown")
            active = acc.get("active", False)
            proxy = acc.get("proxy", "None")
            print(f"  • {username} - Active: {active} - Proxy: {proxy[:30]}..." if proxy else f"  • {username} - Active: {active}")
        else:
            print(f"  • {acc.username} - Active: {acc.active}")


async def main():
    if len(sys.argv) < 2:
        print("\n📌 Usage:")
        print("   python setup.py add    - Add a new worker account")
        print("   python setup.py login  - Login all accounts")
        print("   python setup.py list   - List all accounts")
        return
    
    cmd = sys.argv[1].lower()
    
    if cmd == "add":
        await add_account()
    elif cmd == "login":
        await login_accounts()
    elif cmd == "list":
        await list_accounts()
    else:
        print(f"❌ Unknown command: {cmd}")
        print("   Valid commands: add, login, list")


if __name__ == "__main__":
    asyncio.run(main())
