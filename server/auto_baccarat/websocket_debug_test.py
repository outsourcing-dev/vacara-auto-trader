import asyncio
import json
from fastapi import FastAPI
from playwright.async_api import async_playwright

app = FastAPI()

WS_URL = (
    "wss://tmgoodgame.evo-games.com/public/lobby/socket/v2/"
    "s6ndvz4e27uaykja?messageFormat=json&device=Desktop&features="
    "opensAt%2CmultipleHero%2CshortThumbnails%2CskipInfosPublished%2Csmc%2CuniRouletteHistory%2CbacHistoryV2%2Cfilters%2CtableDecorations"
    "&instance=zq2471-s6ndvz4e27uaykja-"
    "&EVOSESSIONID=s6ndvz4e27uaykjas6n3q6qajw7x4mbh10d86f771827e021ba190bf05202d362270367df8efd8ec8"
    "&client_version=6.20250623.33647.52713-05f17fa7ac"
)

latest_rooms = []

async def run_browser():
    global latest_rooms
    async with async_playwright() as p:
        print("🎯 Playwright Headless 실행")
        browser = await p.chromium.launch(headless=False)  # Headless로 바꿔도 OK
        context = await browser.new_context()
        page = await context.new_page()

        page.on("console", lambda msg: print(f"📢 [Browser Console] {msg.text}"))

        async def handle_message(message):
            try:
                data = json.loads(message)
                if data["type"] == "lobby.historyUpdated":
                    rooms = []
                    for room_id, room in data["args"].items():
                        rooms.append({
                            "room_id": room_id,
                            "results_count": len(room.get("results", []))
                        })
                    latest_rooms.clear()
                    latest_rooms.extend(rooms)
                    print(f"✅ [Python] 최신 방 정보: {rooms}")
            except Exception as e:
                print(f"⚠️ JSON 파싱 실패: {e}")

        await page.expose_function("py_message", handle_message)

        print("🌐 로비 HTML 열기")
        await page.goto("https://tmgoodgame.evo-games.com/")

        print(f"🚀 [Browser] SAME ORIGIN WebSocket 연결")
        await page.evaluate(f"""
            () => {{
                const ws = new WebSocket("{WS_URL}");
                ws.onopen = () => console.log("✅ [Browser] 연결 성공");
                ws.onmessage = ev => {{
                    console.log("📩 [Browser] 메시지:", ev.data.slice(0, 200));
                    window.py_message(ev.data);
                }};
                ws.onerror = ev => console.log("❌ [Browser] 오류:", ev);
                ws.onclose = ev => console.log("🔒 [Browser] 닫힘:", ev);
            }}
        """)

        while True:
            await asyncio.sleep(1)

@app.get("/latest-rooms")
async def get_latest_rooms():
    return {"rooms": latest_rooms}

if __name__ == "__main__":
    import uvicorn

    async def main():
        task_browser = asyncio.create_task(run_browser())
        config = uvicorn.Config(app, host="0.0.0.0", port=8000)
        server = uvicorn.Server(config)
        task_server = asyncio.create_task(server.serve())

        await asyncio.gather(task_browser, task_server)

    asyncio.run(main())
