# test_edge_widget.py
# Automated Microsoft Edge browser test for MindBridge chat widget using Chrome DevTools Protocol (CDP).

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
        return out_path
    return None


async def run_edge_test():
    print("=" * 70)
    print("🌐 AUTOMATED MICROSOFT EDGE BROWSER TEST (CDP)")
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
    # Wait for Edge CDP to become available
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

            print("\n[Step 1] Verifying page title and initial launcher state...")
            title = await eval_js(ws, "document.title", msg_id)
            print(f"Page Title: '{title}'")

            has_launcher = await eval_js(ws, "!!document.getElementById('mindbridge-launcher-btn')", msg_id)
            print(f"Launcher Button Injected: {has_launcher}")
            assert has_launcher, "Launcher button was not injected!"

            # Take screenshot of page with floating launcher button
            await capture_screenshot(ws, "edge_01_launcher_bubble.png", msg_id)

            print("\n[Step 2] Clicking launcher button to open chat window...")
            await eval_js(ws, "document.getElementById('mindbridge-launcher-btn').click();", msg_id)
            await asyncio.sleep(0.5)

            header_title = await eval_js(ws, "document.querySelector('.mindbridge-header-title').innerText", msg_id)
            header_subtitle = await eval_js(ws, "document.querySelector('.mindbridge-header-subtitle').innerText", msg_id)
            print(f"Header Title:    {header_title}")
            print(f"Header Subtitle: {header_subtitle}")

            print("\n[Step 3] Checking automatic opening message & AI disclosure...")
            first_msg = await eval_js(
                ws,
                "document.querySelector('.mindbridge-message.assistant') ? document.querySelector('.mindbridge-message.assistant').innerText : ''",
                msg_id
            )
            print(f"Assistant Opening Message:\n{first_msg}\n")
            assert "AI assistant" in first_msg and "Ellen" in first_msg, "Opening message must clearly disclose AI identity and Ellen persona!"

            # Screenshot showing opened window with upfront AI disclosure
            await capture_screenshot(ws, "edge_02_widget_opened_disclosure.png", msg_id)

            print("\n[Step 4] Sending Turn 1 question: 'What happens if I miss my appointment?'...")
            await eval_js(ws, "document.getElementById('mindbridge-input-field').value = 'What happens if I miss my appointment?';", msg_id)
            await eval_js(ws, "document.getElementById('mindbridge-chat-footer').dispatchEvent(new Event('submit', {bubbles: true, cancelable: true}));", msg_id)

            # Wait for assistant response
            print("Waiting for response from FastAPI backend...")
            reply1 = None
            for _ in range(12):
                await asyncio.sleep(0.5)
                msgs = await eval_js(ws, "Array.from(document.querySelectorAll('.mindbridge-message.assistant')).map(m => m.innerText)", msg_id)
                if len(msgs) >= 2:
                    reply1 = msgs[1]
                    break

            print(f"Assistant Reply 1:\n{reply1}\n")
            assert reply1 and ("24 hours" in reply1 or "cancellation" in reply1.lower()), "Reply should contain cancellation policy details!"

            print("\n[Step 5] Sending Turn 2 follow-up: 'My partner and I keep arguing and we need couples therapy.'...")
            await eval_js(ws, "document.getElementById('mindbridge-input-field').value = 'My partner and I keep arguing and we need couples therapy.';", msg_id)
            await eval_js(ws, "document.getElementById('mindbridge-chat-footer').dispatchEvent(new Event('submit', {bubbles: true, cancelable: true}));", msg_id)

            reply2 = None
            for _ in range(12):
                await asyncio.sleep(0.5)
                msgs = await eval_js(ws, "Array.from(document.querySelectorAll('.mindbridge-message.assistant')).map(m => m.innerText)", msg_id)
                if len(msgs) >= 3:
                    reply2 = msgs[2]
                    break

            print(f"Assistant Reply 2 (Follow-up):\n{reply2}\n")

            # Check sessionStorage session_id
            session_id = await eval_js(ws, "sessionStorage.getItem('mindbridge_session_id')", msg_id)
            print(f"Persisted sessionStorage session_id: {session_id}")
            assert session_id, "sessionStorage must contain session_id!"

            # Final full conversation screenshot
            await capture_screenshot(ws, "edge_03_conversation_flow.png", msg_id)

            print("=" * 70)
            print("✅ MICROSOFT EDGE BROWSER TEST PASSED ALL ASSERTIONS!")
            print("=" * 70)
            return True

    finally:
        proc.kill()
        shutil.rmtree(temp_profile, ignore_errors=True)


if __name__ == "__main__":
    success = asyncio.run(run_edge_test())
    sys.exit(0 if success else 1)
