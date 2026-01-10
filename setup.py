import asyncio
import sys
from twscrape import API, Account
from loguru import logger

async def add_account():
    print("\n--- Add New Worker Account ---")
    username = input("Username: ")
    password = input("Password: ")
    email = input("Email: ")
    email_password = input("Email Password: ")
    
    api = API()
await api.pool.add_account(username, password, email, email_password)
    logger.success(f"Added account: {username}")

async def login_accounts():
    print("\n--- Logging in all accounts to generate cookies ---")
    api = API()
    await api.pool.login_all()
    logger.info("Login process completed. Check logs for details.")

async def main():
    if len(sys.argv) < 2:
        print("Usage: python setup.py [add|login]")
        return

    cmd = sys.argv[1].lower()
    if cmd == "add":
        await add_account()
    elif cmd == "login":
        await login_accounts()
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: python setup.py [add|login]")

if __name__ == "__main__":
    asyncio.run(main())
