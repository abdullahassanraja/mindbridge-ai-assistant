import asyncio
import base64
import json
import shutil
import subprocess
import time
import sys
import urllib.request
from pathlib import Path
import websockets

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
HTML_PATH = Path(r"c:\Users\pc\Documents\mindbridge\widget\index.html").resolve().as_uri()
ARTIFACT_DIR = Path(r"C:\Users\pc\.gemini\antigravity-ide\brain\fa1b549b-89b1-4ff5-82de-6fb3448a7daf")

cmd = [
    EDGE_PATH,
    "--headless=new",
    "--remote-debugging-port=9225",
    "--user-data-dir=C:/temp/edge_test_close_final",
    "--window-size=390,844",
    HTML_PATH,
]
proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(2.0)

async def main():
    try:
        req = urllib.request.urlopen("http://127.0.0.1:9225/json")
        pages = json.loads(req.read().decode("utf-8"))
        ws_url = [p["webSocketDebuggerUrl"] for p in pages if p["type"] == "page"][0]
        async with websockets.connect(ws_url) as ws:
            msg_id = 0
            async def send(method, params=None):
                nonlocal msg_id
                msg_id += 1
                mid = msg_id
                await ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
                while True:
                    resp = json.loads(await ws.recv())
                    if resp.get("id") == mid:
                        return resp.get("result", {})

            async def eval_js(code):
                r = await send("Runtime.evaluate", {"expression": code, "returnByValue": True})
                return r.get("result", {}).get("value")

            async def screenshot(filename):
                res = await send("Page.captureScreenshot", {"format": "jpeg", "quality": 85})
                b64 = res["data"]
                out_path = Path(__file__).resolve().parent / filename
                with open(out_path, "wb") as f:
                    f.write(base64.b64decode(b64))
                print(f"📸 Saved: {filename}")
                try:
                    shutil.copy(str(out_path), str(ARTIFACT_DIR / filename))
                except Exception:
                    pass

            await send("Page.enable")
            await send("Emulation.setDeviceMetricsOverride", {
                "width": 390,
                "height": 844,
                "deviceScaleFactor": 2,
                "mobile": True
            })
            await asyncio.sleep(1.0)

            # 1. Open Chat
            print("\n[Step 1] Opening chat on mobile...")
            await eval_js("window.MindBridge.open()")
            await asyncio.sleep(0.5)

            disp_open = await eval_js("window.getComputedStyle(document.getElementById('mindbridge-chat-window')).display")
            print(f"✓ Chat open display: {disp_open}")
            assert disp_open == "flex", f"Expected flex, got {disp_open}"

            # Verify greeting and chips are displayed
            msg_count = await eval_js("document.querySelectorAll('#mindbridge-message-list .mindbridge-message').length")
            chips_count = await eval_js("document.querySelectorAll('.mindbridge-chip-btn').length")
            print(f"✓ Messages count: {msg_count}, Suggestion chips count: {chips_count}")
            assert msg_count >= 1, "Greeting message missing!"
            assert chips_count == 3, "Suggestion chips missing!"
            await screenshot("mobile_01_chat_opened_with_greeting.jpg")

            # 2. Simulate User Typing & Keyboard Opening
            print("\n[Step 2] Simulating user typing with virtual keyboard open (height: 480)...")
            await eval_js("document.getElementById('mindbridge-input-field').focus()")
            await send("Emulation.setDeviceMetricsOverride", {
                "width": 390,
                "height": 480,
                "deviceScaleFactor": 2,
                "mobile": True
            })
            await eval_js("window.dispatchEvent(new Event('resize'))")
            await asyncio.sleep(0.5)

            header_top = await eval_js("document.getElementById('mindbridge-chat-header').getBoundingClientRect().top")
            header_height = await eval_js("document.getElementById('mindbridge-chat-header').getBoundingClientRect().height")
            footer_bottom = await eval_js("document.getElementById('mindbridge-chat-footer').getBoundingClientRect().bottom")
            print(f"✓ Header top: {header_top}px, Header height: {header_height}px, Footer bottom: {footer_bottom}px")
            assert header_top == 0, f"Header is not at top 0! top={header_top}"
            assert footer_bottom <= 485, f"Footer overflowed keyboard area! bottom={footer_bottom}"

            await screenshot("mobile_02_keyboard_open_latest_messages.jpg")

            # 3. Tap a Suggestion Chip
            print("\n[Step 3] Tapping suggestion chip...")
            await eval_js("document.querySelector('.mindbridge-chip-btn').click()")
            await asyncio.sleep(1.0)
            msg_count_after = await eval_js("document.querySelectorAll('#mindbridge-message-list .mindbridge-message').length")
            print(f"✓ Messages count after chip tap: {msg_count_after}")
            await screenshot("mobile_03_conversation_flowing.jpg")

            # 4. Test Close (Cross) Button
            print("\n[Step 4] Testing Cross (Close) Button...")
            await eval_js("document.getElementById('mindbridge-close-btn').click()")
            await asyncio.sleep(0.5)

            disp_after = await eval_js("window.getComputedStyle(document.getElementById('mindbridge-chat-window')).display")
            container_open = await eval_js("document.getElementById('mindbridge-widget-container').classList.contains('open')")
            launcher_disp = await eval_js("window.getComputedStyle(document.getElementById('mindbridge-launcher-btn')).display")
            body_overflow = await eval_js("document.body.style.overflow")

            print(f"✓ Chat display after close click: {disp_after}")
            print(f"✓ Container has open class: {container_open}")
            print(f"✓ Launcher display: {launcher_disp}")
            print(f"✓ Body overflow restored: '{body_overflow}'")

            assert disp_after == "none", f"Bug: Chat did not close! display={disp_after}"
            assert not container_open, "Container still has open class!"
            assert launcher_disp == "flex", f"Launcher not displayed! display={launcher_disp}"

            await screenshot("mobile_04_closed_back_to_page.jpg")
            print("\n🎉 ALL MOBILE TESTS (FIXED HEADER, MESSAGES FIT, CLOSE BUTTON) PASSED!")

    finally:
        proc.kill()

asyncio.run(main())
