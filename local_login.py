import asyncio
from playwright.async_api import async_playwright

# Proxy Residential Lu (Sacramento, US) - NEW IP
PROXY_CONFIG = {
    "server": "http://45.58.229.242:5414",
    "username": "calponvk",
    "password": "tkhl1oh2f295"
}

async def main():
    print("🚀 Membuka Browser Chrome Lewat Proxy US...")
    
    async with async_playwright() as p:
        # headless=False artinya browser MUNCUL di layar biar lu bisa ketik
        browser = await p.chromium.launch(headless=False) 
        
        context = await browser.new_context(
            proxy=PROXY_CONFIG,
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        page = await context.new_page()
        
        print("🔗 Menuju Login Page Twitter...")
        try:
            await page.goto("https://x.com/i/flow/login", timeout=60000)
        except Exception as e:
            print(f"❌ Gagal konek ke proxy: {e}")
            await browser.close()
            return

        print("\n🛑 TUGAS LU SEKARANG:")
        print("1. Login manual di jendela Chrome yang muncul.")
        print("2. Masukin user/pass/OTP santai aja.")
        print("3. Pastikan sampe masuk halaman HOME.")
        print("4. Kalo udah sukses, balik sini dan TEKAN ENTER.")
        
        input(">> TEKAN ENTER DISINI KALO UDAH LOGIN SUKSES...")
        
        # Ambil Cookies yang udah mateng
        cookies = await context.cookies()
        auth_token = next((c['value'] for c in cookies if c['name'] == 'auth_token'), None)
        ct0 = next((c['value'] for c in cookies if c['name'] == 'ct0'), None)
        
        if auth_token and ct0:
            print("\n" + "="*50)
            print("✅ BERHASIL! INI DATA BUAT VPS:")
            print("="*50)
            print(f"auth_token={auth_token}; ct0={ct0}")
            print("="*50)
            print("Copy baris di atas (auth_token=... sampe titik koma terakhir).")
        else:
            print("❌ Gagal ambil cookies. Pastikan lu udah login sampe Home.")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())