"""Diagnostico Livelo - Chromium + stealth manual (sem biblioteca externa)."""
import asyncio
from playwright.async_api import async_playwright

URL = "https://www.livelo.com.br/juntar-pontos/todos-os-parceiros"

SCRIPT_STEALTH = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt', 'en'] });
window.chrome = { runtime: {} };
"""


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = await browser.new_page(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            locale="pt-BR",
        )
        await page.add_init_script(SCRIPT_STEALTH)
        await page.set_extra_http_headers({"Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"})

        print(f"Navegando ate {URL} ...")
        response = await page.goto(URL, wait_until="networkidle", timeout=30000)
        print(f"Status HTTP: {response.status if response else 'sem resposta'}")

        titulo = await page.title()
        print(f"Titulo: {titulo!r}")

        links = await page.locator("a[href*='/juntar-pontos/parceiros/']").all()
        print(f"Links de parceiro encontrados: {len(links)}")

        for i, link in enumerate(links[:5], start=1):
            href = await link.get_attribute("href")
            texto = await link.inner_text()
            print(f"[{i}] href={href!r} texto={texto!r}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())