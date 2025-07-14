import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)  # headless=False로 하면 창도 뜸
        context = await browser.new_context()
        page = await context.new_page()

        # WebSocket 메시지 수신 이벤트 핸들링
        def on_socket(ws):
            print(f"🔌 WebSocket 연결됨: {ws.url}")

            ws.on("framereceived", lambda frame: print(f"📨 수신: {frame['payload']}"))

        page.on("websocket", on_socket)

        await page.goto("https://tmgoodgame.evo-games.com")  # 실제 연결되는 페이지로 수정 필요
        await asyncio.sleep(15)  # WebSocket 열리고 메시지 수신할 시간 확보

        await browser.close()

asyncio.run(main())
