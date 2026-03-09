import asyncio
from getpass import getpass
from urllib.parse import urlparse


try:
    from playwright_stealth import stealth_async
except ModuleNotFoundError:
    stealth_async = None


async def apply_stealth(page) -> None:
    if stealth_async:
        await stealth_async(page)
        return

    await page.add_init_script(
        """
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4]});
        Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        window.chrome = { runtime: {} };
        """
    )


def parse_proxy(proxy_string: str) -> dict | None:
    proxy = proxy_string.strip()
    if not proxy:
        return None
    parsed = urlparse(proxy)
    if not parsed.scheme or not parsed.hostname or not parsed.port:
        raise ValueError("Proxy must be in the format http://user:pass@host:port")

    proxy_payload = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"}
    if parsed.username:
        proxy_payload["username"] = parsed.username
    if parsed.password:
        proxy_payload["password"] = parsed.password
    return proxy_payload


async def wait_and_fill(page, selector: str, value: str, timeout: int = 30_000) -> None:
    await page.wait_for_selector(selector, timeout=timeout)
    await page.fill(selector, value)


async def maybe_handle_text_challenge(page) -> None:
    text_input = await page.query_selector('input[name="text"]')
    if not text_input:
        return

    print("X requested additional verification information.")
    challenge_value = input("Enter the requested value (email, phone, username, or OTP): ").strip()
    await page.fill('input[name="text"]', challenge_value)
    await page.keyboard.press("Enter")
    await asyncio.sleep(3)


async def main() -> None:
    try:
        from playwright.async_api import TimeoutError as PlaywrightTimeout
        from playwright.async_api import async_playwright
    except ModuleNotFoundError as exc:
        raise SystemExit("Playwright is not installed. Run `pip install -r requirements.txt` first.") from exc

    username = input("Twitter username (without @): ").strip()
    password = getpass("Twitter password: ").strip()
    proxy_string = input("Proxy (http://user:pass@host:port) [optional]: ").strip()
    proxy = parse_proxy(proxy_string) if proxy_string else None

    print("Launching stealth browser. Screenshots are written to debug_*.png if the flow gets stuck.")

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ],
            proxy=proxy,
        )
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="en-US",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()
        await apply_stealth(page)

        try:
            await page.goto("https://x.com/i/flow/login", wait_until="networkidle")
            await page.screenshot(path="debug_01_login_page.png")

            await wait_and_fill(page, 'input[autocomplete="username"]', username)
            await page.keyboard.press("Enter")
            await asyncio.sleep(3)

            for attempt in range(5):
                password_field = await page.query_selector('input[name="password"]')
                if password_field:
                    break
                await page.screenshot(path=f"debug_step_{attempt + 1}.png")
                await maybe_handle_text_challenge(page)
                await asyncio.sleep(2)
            else:
                raise RuntimeError("Password field never appeared. Check debug screenshots.")

            await page.fill('input[name="password"]', password)
            await page.keyboard.press("Enter")
            await asyncio.sleep(5)

            try:
                await page.wait_for_url("**/home**", timeout=30_000)
            except PlaywrightTimeout:
                await page.screenshot(path="debug_login_timeout.png")
                await maybe_handle_text_challenge(page)
                await page.wait_for_url("**/home**", timeout=30_000)

            cookies = await context.cookies()
            auth_token = next((cookie["value"] for cookie in cookies if cookie["name"] == "auth_token"), None)
            ct0 = next((cookie["value"] for cookie in cookies if cookie["name"] == "ct0"), None)

            if auth_token and ct0:
                print("Login succeeded. Use this cookie string with `python setup.py manual-add`:")
                print(f"auth_token={auth_token}; ct0={ct0}")
            else:
                raise RuntimeError("Login succeeded but auth_token/ct0 were not present.")
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
