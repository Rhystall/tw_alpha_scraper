import asyncio
from urllib.parse import urlparse


def _build_proxy_config(proxy_string: str):
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


async def main() -> None:
    try:
        from playwright.async_api import async_playwright
    except ModuleNotFoundError as exc:
        raise SystemExit("Playwright is not installed. Run `pip install -r requirements.txt` first.") from exc

    proxy_string = input("Proxy (http://user:pass@host:port) [optional]: ").strip()
    proxy_config = _build_proxy_config(proxy_string) if proxy_string else None

    print("Launching browser. Complete the login flow manually, then press Enter here.")

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False, proxy=proxy_config)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()
        await page.goto("https://x.com/i/flow/login", timeout=60_000)

        input("Press Enter after you have reached the X home timeline...")

        cookies = await context.cookies()
        auth_token = next((cookie["value"] for cookie in cookies if cookie["name"] == "auth_token"), None)
        ct0 = next((cookie["value"] for cookie in cookies if cookie["name"] == "ct0"), None)

        if auth_token and ct0:
            print("Use the following cookie string with `python setup.py manual-add`:")
            print(f"auth_token={auth_token}; ct0={ct0}")
        else:
            print("Could not find auth_token/ct0. Make sure the login completed successfully.")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
