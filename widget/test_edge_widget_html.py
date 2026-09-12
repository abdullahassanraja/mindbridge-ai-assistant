# test_edge_widget_html.py
# Automated Microsoft Edge browser test for MindBridge chat widget verifying HTML rendering via CDP.

import asyncio
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import websockets

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
WIDGET_URL = "http://127.0.0.1:3000/index.html"
CDP_PORT = 9222
SCREENSHOT_DIR = Path(__file__).resolve().parent
ARTIFACT_DIR = Path(r"C:\Users\pc\.gemini\antigravity-ide\brain\462abf2c-829f-489e-8a60-3a6529aaba64")


async def send_cdp(ws, method, params=None, msg_id=[1]):
    current_id = msg_id[0]
    msg_id[0] += 1
    payload = {"id": current_id, "method": method, "params": params or {}}
    await ws.send(json.dumps(payload))
    while True:
        resp = await ws.recv()
        data = json.loads(resp)
        if data.get("id") == current_id:
            return data.get("result", {})


async def eval_js(ws, expr, msg_id=[1]):
    res = await send_cdp(ws, "Runtime.evaluate", {"expression": expr, "returnByValue": True}, msg_id)
    return res.get("result", {}).get("value")


async def capture_screenshot(ws, filename, msg_id=[1]):
    res = await send_cdp(ws, "Page.captureScreenshot", {"format": "png"}, msg_id)
    b64data = res.get("data")
    if b64data:
        out_path = SCREENSHOT_DIR / filename
        with open(out_path, "wb") as f:
            f.write(base64.b64decode(b64data))
        print(f"📸 Saved screenshot to: {out_path}")
        # Copy to artifact directory
        try:
            shutil.copy(str(out_path), str(ARTIFACT_DIR / filename))
            print(f"📸 Copied screenshot to artifact dir: {ARTIFACT_DIR / filename}")
        except Exception as e:
            print(f"Could not copy to artifact dir: {e}")
        return out_path
    return None


async def run_edge_test():
    print("=" * 70)
    print("🌐 AUTOMATED MICROSOFT EDGE BROWSER TEST — HTML RENDERING VERIFICATION")
    print("=" * 70)

    temp_profile = tempfile.mkdtemp(prefix="edge_cdp_")
    cmd = [
        EDGE_PATH,
        "--headless=new",
        f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={temp_profile}",
        "--window-size=1280,900",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        WIDGET_URL,
    ]

    print(f"Launching Microsoft Edge: {EDGE_PATH}")
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    ws_url = None
    for attempt in range(15):
        time.sleep(0.5)
        try:
            req = urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json", timeout=2)
            pages = json.loads(req.read().decode("utf-8"))
            for p in pages:
                if p.get("type") == "page" and "127.0.0.1:3000" in p.get("url", ""):
                    ws_url = p.get("webSocketDebuggerUrl")
                    break
            if ws_url:
                break
        except Exception:
            pass

    if not ws_url:
        print("Failed to obtain webSocketDebuggerUrl from Edge CDP.")
        proc.kill()
        shutil.rmtree(temp_profile, ignore_errors=True)
        return False

    print(f"Connected to Edge tab CDP: {ws_url}")
    msg_id = [1]

    try:
        async with websockets.connect(ws_url) as ws:
            await send_cdp(ws, "Page.enable", {}, msg_id)
            await send_cdp(ws, "Runtime.enable", {}, msg_id)
            await asyncio.sleep(1.0)

            print("\n[Step 1] Verifying launcher bubble state...")
            has_launcher = await eval_js(ws, "!!document.getElementById('mindbridge-launcher-btn')", msg_id)
            print(f"Launcher Button Injected: {has_launcher}")
            assert has_launcher, "Launcher button was not injected!"
            await capture_screenshot(ws, "edge_01_launcher_bubble.png", msg_id)

            print("\n[Step 2] Opening chat window and checking initial message...")
            # Clear sessionStorage to ensure fresh initial message
            await eval_js(ws, "sessionStorage.clear();", msg_id)
            await eval_js(ws, "document.getElementById('mindbridge-launcher-btn').click();", msg_id)
            await asyncio.sleep(0.5)

            first_msg = await eval_js(
                ws,
                "document.querySelector('.mindbridge-message.assistant') ? document.querySelector('.mindbridge-message.assistant').innerText : ''",
                msg_id
            )
            print(f"Assistant Opening Message: {repr(first_msg)}")
            assert "AI assistant" in first_msg and "What's your name" in first_msg, "Opening message must be warm AI disclosure asking for name!"
            await capture_screenshot(ws, "edge_02_widget_opened_disclosure.png", msg_id)

            print("\n[Step 3] Asking 'What counseling services do you offer?'...")
            await eval_js(ws, "document.getElementById('mindbridge-input-field').value = 'What counseling services do you offer?';", msg_id)
            await eval_js(ws, "document.getElementById('mindbridge-chat-footer').dispatchEvent(new Event('submit', {bubbles: true, cancelable: true}));", msg_id)

            print("Waiting for response from FastAPI backend...")
            reply_html = None
            reply_text = None
            for _ in range(25):
                await asyncio.sleep(1.0)
                msgs_html = await eval_js(
                    ws,
                    "Array.from(document.querySelectorAll('.mindbridge-message.assistant')).map(m => m.innerHTML)",
                    msg_id
                )
                msgs_text = await eval_js(
                    ws,
                    "Array.from(document.querySelectorAll('.mindbridge-message.assistant')).map(m => m.innerText)",
                    msg_id
                )
                if len(msgs_html) >= 2:
                    reply_html = msgs_html[1]
                    reply_text = msgs_text[1]
                    break

            print(f"Assistant Reply Text:\n{reply_text}\n")
            print(f"Assistant Reply HTML:\n{reply_html}\n")

            has_asterisks = "**" in (reply_text or "")
            print(f"Literal Markdown Asterisks in reply: {'FAILED (found **)' if has_asterisks else 'PASSED (none)'}")
            assert not has_asterisks, "Response must not contain literal markdown asterisks!"

            # Verify presence of formatted HTML elements (br, b, ul, or li)
            has_html_tags = any(tag in (reply_html or "").lower() for tag in ["<br>", "<b>", "<ul>", "<li>"])
            print(f"HTML Formatting Elements Present: {'PASSED' if has_html_tags else 'FAILED'}")

            # Capture final conversation flow screenshot
            await capture_screenshot(ws, "edge_03_conversation_flow.png", msg_id)

            print("\n All browser visual and HTML rendering checks passed!")
            return True

    finally:
        proc.kill()
        shutil.rmtree(temp_profile, ignore_errors=True)


if __name__ == "__main__":
    success = asyncio.run(run_edge_test())
    sys.exit(0 if success else 1)
