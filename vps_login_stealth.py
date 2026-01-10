"""
vps_login_stealth.py - Playwright-based Twitter login with stealth mode.

Bypasses Cloudflare 403 blocks by using a real headless browser with
stealth fingerprinting. Extracts cookies and saves them to twscrape.

Requirements:
    pip install playwright playwright-stealth
    playwright install chromium
"""

import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from playwright_stealth import stealth_async
from twscrape import API
from loguru import logger


async def wait_and_fill(page, selector: str, value: str, timeout: int = 30000):
    """Wait for element and fill with value."""
    await page.wait_for_selector(selector, timeout=timeout)
    await page.fill(selector, value)


async def check_for_challenge(page) -> str | None:
    """Check if Twitter is asking for additional verification."""
    try:
        # Check for "Unusual login activity" or verification prompts
        unusual_text = await page.query_selector('text="Verify your identity"')
        if unusual_text:
            return "identity"
        
        email_text = await page.query_selector('text="Enter your phone number or email"')
        if email_text:
            return "email_phone"
        
        phone_text = await page.query_selector('text="Enter your phone number"')
        if phone_text:
            return "phone"
            
        otp_text = await page.query_selector('text="Enter your verification code"')
        if otp_text:
            return "otp"
            
        auth_app_text = await page.query_selector('text="Enter the code from your authenticator app"')
        if auth_app_text:
            return "2fa"
            
    except Exception:
        pass
    return None


async def handle_challenge(page, challenge_type: str):
    """Handle various Twitter security challenges."""
    if challenge_type == "email_phone":
        print("\n" + "=" * 50)
        print("⚠️  UNUSUAL ACTIVITY DETECTED")
        print("Twitter is asking for your email or phone number.")
        print("=" * 50)
        value = input("Enter your email or phone: ").strip()
        await wait_and_fill(page, 'input[name="text"]', value)
        await page.keyboard.press("Enter")
        await asyncio.sleep(3)
        
    elif challenge_type == "phone":
        print("\n" + "=" * 50)
        print("⚠️  PHONE VERIFICATION REQUIRED")
        print("=" * 50)
        value = input("Enter your phone number: ").strip()
        await wait_and_fill(page, 'input[name="text"]', value)
        await page.keyboard.press("Enter")
        await asyncio.sleep(3)
        
    elif challenge_type in ["otp", "2fa"]:
        print("\n" + "=" * 50)
        print("🔐 2FA VERIFICATION REQUIRED")
        print("Enter the code from your authenticator app or SMS.")
        print("=" * 50)
        code = input("Enter OTP/2FA code: ").strip()
        await wait_and_fill(page, 'input[name="text"]', code)
        await page.keyboard.press("Enter")
        await asyncio.sleep(3)
        
    elif challenge_type == "identity":
        print("\n" + "=" * 50)
        print("⚠️  IDENTITY VERIFICATION REQUIRED")
        print("Twitter is asking to verify your identity.")
        print("=" * 50)
        value = input("Enter verification info: ").strip()
        await wait_and_fill(page, 'input[name="text"]', value)
        await page.keyboard.press("Enter")
        await asyncio.sleep(3)


async def extract_cookies(context) -> dict:
    """Extract auth cookies from browser context."""
    cookies = await context.cookies()
    cookie_dict = {}
    for cookie in cookies:
        if cookie["name"] in ["auth_token", "ct0", "guest_id", "twid", "kdt"]:
            cookie_dict[cookie["name"]] = cookie["value"]
    return cookie_dict


async def cookies_to_string(cookie_dict: dict) -> str:
    """Convert cookie dict to string format."""
    return "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])


async def save_to_twscrape(username: str, password: str, email: str, email_pass: str, cookie_str: str):
    """Save account with cookies to twscrape database."""
    api = API()
    
    # Delete existing account if any
    try:
        await api.pool.delete_accounts([username])
        logger.warning(f"Deleted existing account: {username}")
    except Exception:
        pass
    
    # Add account with cookies
    await api.pool.add_account(
        username=username,
        password=password,
        email=email,
        email_password=email_pass,
        cookies=cookie_str
    )
    logger.success(f"Account {username} saved to twscrape with cookies!")


async def playwright_login():
    print("\n" + "=" * 60)
    print("   🚀 VPS STEALTH LOGIN - Playwright + Stealth Mode")
    print("=" * 60 + "\n")
    
    # Get credentials
    username = input("Twitter Username (without @): ").strip()
    password = input("Twitter Password: ").strip()
    email = input("Email (for twscrape): ").strip()
    email_pass = input("Email Password (for twscrape): ").strip()
    
    print("\n🔄 Launching stealth browser...")
    
    async with async_playwright() as p:
        # Launch browser with stealth settings
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ]
        )
        
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US",
        )
        
        page = await context.new_page()
        
        # Apply stealth
        await stealth_async(page)
        
        try:
            # Navigate to login
            logger.info("Navigating to Twitter login...")
            await page.goto("https://x.com/i/flow/login", wait_until="networkidle")
            await asyncio.sleep(3)
            
            # Screenshot for debugging
            await page.screenshot(path="debug_01_login_page.png")
            logger.info("Screenshot saved: debug_01_login_page.png")
            
            # Step 1: Enter username
            logger.info("Entering username...")
            await wait_and_fill(page, 'input[autocomplete="username"]', username)
            await page.keyboard.press("Enter")
            await asyncio.sleep(3)
            
            # Check for challenges after username
            challenge = await check_for_challenge(page)
            if challenge:
                await handle_challenge(page, challenge)
            
            # Step 2: Enter password
            logger.info("Entering password...")
            try:
                await wait_and_fill(page, 'input[name="password"]', password, timeout=10000)
                await page.keyboard.press("Enter")
                await asyncio.sleep(5)
            except PlaywrightTimeout:
                await page.screenshot(path="debug_02_password_issue.png")
                logger.error("Password field not found. Check debug_02_password_issue.png")
                raise
            
            # Check for 2FA
            challenge = await check_for_challenge(page)
            if challenge:
                await handle_challenge(page, challenge)
            
            # Wait for successful login
            logger.info("Waiting for login to complete...")
            try:
                await page.wait_for_url("**/home**", timeout=30000)
            except PlaywrightTimeout:
                # Check if we're stuck on a challenge
                challenge = await check_for_challenge(page)
                if challenge:
                    await handle_challenge(page, challenge)
                    await page.wait_for_url("**/home**", timeout=30000)
                else:
                    await page.screenshot(path="debug_03_login_stuck.png")
                    logger.error("Login seems stuck. Check debug_03_login_stuck.png")
                    raise
            
            logger.success("✅ Login successful!")
            await page.screenshot(path="debug_success.png")
            
            # Extract cookies
            logger.info("Extracting cookies...")
            cookie_dict = await extract_cookies(context)
            
            if "auth_token" not in cookie_dict or "ct0" not in cookie_dict:
                logger.error("Required cookies not found!")
                logger.error(f"Found cookies: {list(cookie_dict.keys())}")
                raise Exception("Missing auth_token or ct0 cookie")
            
            cookie_str = await cookies_to_string(cookie_dict)
            logger.info(f"Cookies extracted: {list(cookie_dict.keys())}")
            
            # Save to twscrape
            await save_to_twscrape(username, password, email, email_pass, cookie_str)
            
            print("\n" + "=" * 60)
            print("   ✅ SUCCESS! Account ready for monitor.py")
            print("=" * 60)
            print("\nRun: python monitor.py")
            
        except Exception as e:
            await page.screenshot(path="debug_error.png")
            logger.error(f"Login failed: {e}")
            logger.error("Check debug_error.png for details")
            raise
        finally:
            await browser.close()


async def main():
    logger.add("vps_login.log", rotation="10 MB")
    await playwright_login()


if __name__ == "__main__":
    asyncio.run(main())
