# test_edge_landing_vibe.py
# Automated Microsoft Edge Browser Test for MindBridge / Ellen Landing Page
# Tests reference UI cloning, vibe-coded young therapist section, and mobile fixed-header bug fix.

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
HTML_PATH = Path(r"c:\Users\pc\Documents\mindbridge\widget\index.html").resolve()
WIDGET_URL = HTML_PATH.as_uri()
CDP_PORT = 9222
SCREENSHOT_DIR = Path(__file__).resolve().parent
ARTIFACT_DIR = Path(r"C:\Users\pc\.gemini\antigravity-ide\brain\fa1b549b-89b1-4ff5-82de-6fb3448a7daf")

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
    fmt = "jpeg" if filename.endswith(".jpg") or filename.endswith(".jpeg") else "png"
    params = {"format": fmt}
    if fmt == "jpeg":
        params["quality"] = 85
    res = await send_cdp(ws, "Page.captureScreenshot", params, msg_id)
    b64data = res.get("data")
    if b64data:
        out_path = SCREENSHOT_DIR / filename
        with open(out_path, "wb") as f:
            f.write(base64.b64decode(b64data))
        print(f"📸 Saved screenshot: {filename}")
        try:
            shutil.copy(str(out_path), str(ARTIFACT_DIR / filename))
            print(f"   ↳ Copied to artifact directory: {ARTIFACT_DIR / filename}")
        except Exception as e:
            print(f"   ↳ Note: Could not copy to artifact dir: {e}")
        return out_path
    return None

async def run_edge_vibe_test():
    print("=" * 70)
    print("🌐 AUTOMATED MICROSOFT EDGE BROWSER TEST — VIBE & FIXED HEADER VERIFICATION")
    print("=" * 70)
    print(f"Edge Path: {EDGE_PATH}")
    print(f"Loading URL: {WIDGET_URL}")

    temp_profile = tempfile.mkdtemp(prefix="edge_vibe_cdp_")
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

    print("Launching Microsoft Edge...")
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    ws_url = None
    for attempt in range(20):
        time.sleep(0.5)
        try:
            req = urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json", timeout=2)
            pages = json.loads(req.read().decode("utf-8"))
            for p in pages:
                if p.get("type") == "page":
                    ws_url = p.get("webSocketDebuggerUrl")
                    break
            if ws_url:
                break
        except Exception:
            pass

    if not ws_url:
        print("❌ Failed to obtain webSocketDebuggerUrl from Edge CDP.")
        proc.kill()
        shutil.rmtree(temp_profile, ignore_errors=True)
        return False

    print(f"✓ Connected to Microsoft Edge CDP: {ws_url}")
    msg_id = [1]

    try:
        async with websockets.connect(ws_url, max_size=30 * 1024 * 1024) as ws:
            await send_cdp(ws, "Page.enable", {}, msg_id)
            await send_cdp(ws, "Runtime.enable", {}, msg_id)
            await asyncio.sleep(1.5)

            # 1. Capture Desktop Hero Section
            print("\n[Step 1] Capturing Desktop Hero & Navigation...")
            await capture_screenshot(ws, "edge_vibe_01_hero.jpg", msg_id)

            # 2. Scroll to Vibe Young Therapist Section
            print("\n[Step 2] Scrolling to Vibe-Coded Young Therapist Section...")
            await eval_js(ws, "document.getElementById('vibe-therapist').scrollIntoView({behavior: 'instant'});", msg_id)
            await asyncio.sleep(0.8)
            await capture_screenshot(ws, "edge_vibe_02_young_therapist.jpg", msg_id)

            # 3. Scroll to Simple Steps Section
            print("\n[Step 3] Scrolling to Simple Steps Section...")
            await eval_js(ws, "document.getElementById('steps').scrollIntoView({behavior: 'instant'});", msg_id)
            await asyncio.sleep(0.8)
            await capture_screenshot(ws, "edge_vibe_03_simple_steps.jpg", msg_id)

            # 4. Scroll to Why Safe Section
            print("\n[Step 4] Scrolling to Why People Feel Safe Section...")
            await eval_js(ws, "document.getElementById('why-safe').scrollIntoView({behavior: 'instant'});", msg_id)
            await asyncio.sleep(0.8)
            await capture_screenshot(ws, "edge_vibe_04_why_safe.jpg", msg_id)

            # 5. Scroll to Clinicians & FAQ Section
            print("\n[Step 5] Scrolling to Clinicians & FAQ Section...")
            await eval_js(ws, "document.getElementById('therapists').scrollIntoView({behavior: 'instant'});", msg_id)
            await asyncio.sleep(0.8)
            await capture_screenshot(ws, "edge_vibe_05_clinicians.jpg", msg_id)

            # 6. Test Chat Widget Opening on Desktop
            print("\n[Step 6] Opening Ellen chat widget on Desktop...")
            await eval_js(ws, "if (window.MindBridge) window.MindBridge.open();", msg_id)
            await asyncio.sleep(1.0)
            is_open = await eval_js(ws, "document.getElementById('mindbridge-chat-window').style.display === 'flex'", msg_id)
            print(f"Chat window open state: {is_open}")
            assert is_open, "Chat window should be open!"
            await capture_screenshot(ws, "edge_vibe_06_desktop_chat.jpg", msg_id)

            # 7. Mobile Viewport Emulation & Chat Header Pin Test
            print("\n[Step 7] Emulating Mobile Viewport (iPhone / Pixel 390x844)...")
            await send_cdp(ws, "Emulation.setDeviceMetricsOverride", {
                "width": 390,
                "height": 844,
                "deviceScaleFactor": 2,
                "mobile": True
            }, msg_id)
            await asyncio.sleep(0.5)

            # Trigger mobile layout sync
            await eval_js(ws, "window.dispatchEvent(new Event('resize'));", msg_id)
            await asyncio.sleep(0.5)

            # Check header position
            header_rect = await eval_js(ws, """
                (() => {
                    const h = document.getElementById('mindbridge-chat-header');
                    const r = h.getBoundingClientRect();
                    return { top: r.top, height: r.height, bottom: r.bottom };
                })()
            """, msg_id)
            print(f"Mobile Header Rect: {header_rect}")

            # Verify header is at top: top should be 0
            assert header_rect['top'] == 0, f"Chat header top is not 0! top={header_rect['top']}"
            print("✓ Mobile Chat Header is firmly at top=0.")

            # 8. Simulate Input Focus (Virtual Keyboard Opening)
            print("\n[Step 8] Simulating Virtual Keyboard Opening (Focusing input & shrinking visual viewport)...")
            # Focus input field
            await eval_js(ws, "document.getElementById('mindbridge-input-field').focus();", msg_id)
            await asyncio.sleep(0.3)

            # Emulate virtual keyboard by resizing viewport to height=480 (keyboard takes bottom ~364px)
            await send_cdp(ws, "Emulation.setDeviceMetricsOverride", {
                "width": 390,
                "height": 480,
                "deviceScaleFactor": 2,
                "mobile": True
            }, msg_id)
            await eval_js(ws, "window.dispatchEvent(new Event('resize'));", msg_id)
            await asyncio.sleep(0.5)

            header_rect_kb = await eval_js(ws, """
                (() => {
                    const h = document.getElementById('mindbridge-chat-header');
                    const r = h.getBoundingClientRect();
                    return { top: r.top, height: r.height, bottom: r.bottom };
                })()
            """, msg_id)
            print(f"Mobile Header Rect with Virtual Keyboard Open: {header_rect_kb}")
            assert header_rect_kb['top'] == 0, f"Bug: Header moved up when keyboard opened! top={header_rect_kb['top']}"
            print("✅ BUG FIXED: Mobile chat header remains fixed at top=0 even when keyboard is open!")

            # Capture mobile keyboard open screenshot
            await capture_screenshot(ws, "edge_vibe_07_mobile_fixed_header.jpg", msg_id)

            print("\n" + "=" * 70)
            print("✅ ALL MICROSOFT EDGE BROWSER & VIBE CHECKS PASSED SUCCESSFULLY!")
            print("=" * 70)
            return True

    finally:
        proc.kill()
        shutil.rmtree(temp_profile, ignore_errors=True)

if __name__ == "__main__":
    success = asyncio.run(run_edge_vibe_test())
    sys.exit(0 if success else 1)
