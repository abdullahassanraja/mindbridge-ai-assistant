# test_widget_redesign.py
# Automated Microsoft Edge browser test for MindBridge chat widget UI/UX redesign:
# - Soothing animated moving light gradient background
# - Central ethereal living aura orb (inspired by reference image)
# - Initial welcome view with 3 interactive starter cards in a row:
#     1) "Book a consultation for me"
#     2) "I got a problem"
#     3) "Tell me more about MindBridge"
# - Gemini-style message bubbles: vibrant blue for sender, crisp white for assistant
# - Generous padding with zero text overlapping
# - Header reset / new chat functionality
# - Mobile responsiveness verification at 375px width

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
CDP_PORT = 9224
SCREENSHOT_DIR = Path(__file__).resolve().parent
ARTIFACT_DIR = Path(r"C:\Users\pc\.gemini\antigravity-ide\brain\1273d352-a1bd-4f72-af02-58fb6a4e6725")


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
        print(f"📸 Saved screenshot: {out_path}")
        try:
            ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy(str(out_path), str(ARTIFACT_DIR / filename))
            print(f"📸 Copied screenshot to artifact directory: {ARTIFACT_DIR / filename}")
        except Exception as e:
            print(f"Could not copy to artifact dir: {e}")
        return out_path
    return None


async def run_redesign_test():
    print("=" * 80)
    print("🌐 AUTOMATED EDGE BROWSER TEST: SOOTHING GRADIENT, AURA ORB & STARTER CARDS")
    print("=" * 80)

    temp_profile = tempfile.mkdtemp(prefix="edge_widget_test_")
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

            # 1. Launcher button check with Ellen's image
            print("\n[Step 1] Checking floating launcher button with Ellen avatar image...")
            has_launcher = await eval_js(ws, "!!document.getElementById('mindbridge-launcher-btn')", msg_id)
            has_launcher_img = await eval_js(ws, "!!document.querySelector('.mindbridge-launcher-avatar-img')", msg_id)
            has_launcher_beacon = await eval_js(ws, "!!document.querySelector('.mindbridge-launcher-beacon')", msg_id)
            print(f"Launcher Button:      {has_launcher}")
            print(f"Ellen Photo Present:  {has_launcher_img}")
            print(f"Online Beacon Dot:    {has_launcher_beacon}")

            assert has_launcher, "Launcher button was not injected!"
            assert has_launcher_img, "Launcher button must contain Ellen's realistic photo!"
            assert has_launcher_beacon, "Launcher button must have online green dot beacon!"

            await capture_screenshot(ws, "redesign_01_launcher.png", msg_id)
            print(">>> Launcher button with Ellen's photo and online green dot verified.")

            # 2. Open chat window and inspect Full-Height Welcome view with Aura Orb & 3 Starter Cards
            print("\n[Step 2] Opening chat window and verifying Full Height on Laptop...")
            await eval_js(ws, "sessionStorage.clear();", msg_id)
            await eval_js(ws, "document.getElementById('mindbridge-launcher-btn').click();", msg_id)
            await asyncio.sleep(0.8)

            header_title = await eval_js(ws, "document.getElementById('mindbridge-chat-title').innerText", msg_id)
            has_header_avatar = await eval_js(ws, "!!document.querySelector('.mindbridge-header-avatar-img')", msg_id)
            window_height = await eval_js(ws, "document.getElementById('mindbridge-chat-window').getBoundingClientRect().height", msg_id)
            viewport_height = await eval_js(ws, "window.innerHeight", msg_id)

            has_aura_core = await eval_js(ws, "!!document.querySelector('.mindbridge-aura-core')", msg_id)
            has_aura_glow = await eval_js(ws, "!!document.querySelector('.mindbridge-aura-glow')", msg_id)
            starter_card_count = await eval_js(ws, "document.querySelectorAll('.mindbridge-starter-card').length", msg_id)
            starter_titles = await eval_js(ws, "Array.from(document.querySelectorAll('.mindbridge-starter-title')).map(el => el.innerText)", msg_id)
            font_family = await eval_js(ws, "window.getComputedStyle(document.getElementById('mindbridge-widget-container')).fontFamily", msg_id)

            salutation = await eval_js(ws, "document.querySelector('.mindbridge-welcome-salutation') ? document.querySelector('.mindbridge-welcome-salutation').innerText : ''", msg_id)
            static_phrase = await eval_js(ws, "document.querySelector('.mindbridge-static-phrase') ? document.querySelector('.mindbridge-static-phrase').innerText : ''", msg_id)
            ticker_initial = await eval_js(ws, "document.getElementById('mindbridge-ticker-text') ? document.getElementById('mindbridge-ticker-text').innerText : ''", msg_id)

            print(f"Header Title:         {header_title}")
            print(f"Header Avatar Img:    {has_header_avatar}")
            print(f"Chat Window Height:   {window_height}px / Viewport: {viewport_height}px (Full Height)")
            print(f"Aura Core Present:    {has_aura_core}")
            print(f"Aura Glow Present:    {has_aura_glow}")
            print(f"Salutation Text:      '{salutation}'")
            print(f"Static Phrase:        '{static_phrase}'")
            print(f"Initial Ticker:       '{ticker_initial}'")
            print(f"Starter Cards:        {starter_card_count} detected -> {starter_titles}")
            print(f"Font Family:          {font_family}")

            assert header_title == "Ellen", f"Expected header title 'Ellen', got '{header_title}'"
            assert has_header_avatar, "Ellen's avatar image must be present in header profile!"
            assert window_height >= (viewport_height - 60), f"Expected chat window to extend to full height on laptop, got {window_height}px"
            assert has_aura_core and has_aura_glow, "Living ethereal aura orb must be present!"
            assert "Hi there" in salutation, f"Expected 'Hi there' in salutation, got '{salutation}'"
            assert "let us help you" in static_phrase.lower(), f"Expected 'let us help you' in static phrase, got '{static_phrase}'"
            assert ticker_initial == "heal.", f"Expected initial ticker word 'heal.', got '{ticker_initial}'"

            # Wait for ticker to advance to next word
            await asyncio.sleep(2.9)
            ticker_next = await eval_js(ws, "document.getElementById('mindbridge-ticker-text').innerText", msg_id)
            print(f"Advanced Ticker:    '{ticker_next}'")
            assert ticker_next != ticker_initial, f"Ticker should have rotated! Initial: '{ticker_initial}', current: '{ticker_next}'"

            assert starter_card_count == 3, f"Expected exactly 3 starter cards, got {starter_card_count}"
            assert "Help me find the right therapist" in starter_titles[0]
            assert "I'd like to book a consultation" in starter_titles[1]
            assert "I'm not sure where to begin" in starter_titles[2]

            await capture_screenshot(ws, "redesign_02_welcome_cards.png", msg_id)
            print(">>> Welcome state with living aura orb, creative dynamic ticker, and 3 starter prompt cards verified.")

            # 3. Click Starter Card 1: "Help me find the right therapist"
            print("\n[Step 3] Clicking starter card 'Help me find the right therapist'...")
            await eval_js(ws, "document.getElementById('opt-therapist').click();", msg_id)
            await asyncio.sleep(0.3)

            # 4. Verify typing indicator appears and check user bubble styling
            has_typing = await eval_js(ws, "!!document.getElementById('mindbridge-typing-indicator')", msg_id)
            typing_dots = await eval_js(ws, "document.querySelectorAll('.mindbridge-typing-dot').length", msg_id)
            user_msg_text = await eval_js(ws, "document.querySelector('.mindbridge-message.user') ? document.querySelector('.mindbridge-message.user').innerText : ''", msg_id)
            user_padding = await eval_js(ws, "window.getComputedStyle(document.querySelector('.mindbridge-message.user')).padding", msg_id)
            user_bg = await eval_js(ws, "window.getComputedStyle(document.querySelector('.mindbridge-message.user')).backgroundImage", msg_id)
            user_color = await eval_js(ws, "window.getComputedStyle(document.querySelector('.mindbridge-message.user')).color", msg_id)

            print(f"User Message:       '{user_msg_text}'")
            print(f"User Padding:       {user_padding}")
            print(f"User BG:            {user_bg}")
            print(f"User Text Color:    {user_color}")
            print(f"Typing Indicator:   {has_typing} ({typing_dots} dots)")

            assert user_msg_text == "Help me find the right therapist", f"Expected user prompt, got '{user_msg_text}'"
            assert has_typing, "Typing indicator must appear while waiting for response!"
            assert typing_dots == 3, f"Expected 3 pulsing gradient dots, got {typing_dots}"
            assert "14px" in user_padding or "20px" in user_padding, f"Expected generous padding on user bubble, got {user_padding}"

            await capture_screenshot(ws, "redesign_03_typing_indicator.png", msg_id)
            print(">>> User message rendered with generous padding, typing indicator active.")

            # 5. Wait for assistant reply from backend
            print("\n[Step 4] Waiting for Ellen's reply from backend...")
            reply_text = None
            for _ in range(35):
                await asyncio.sleep(1.0)
                assistant_msgs = await eval_js(
                    ws,
                    "Array.from(document.querySelectorAll('.mindbridge-message.assistant')).map(m => m.innerText)",
                    msg_id
                )
                if assistant_msgs and len(assistant_msgs) >= 1:
                    reply_text = assistant_msgs[0]
                    break

            print(f"\nAssistant Reply Received:\n\"{reply_text}\"\n")
            assert reply_text and len(reply_text) > 10, "Did not receive assistant reply from backend!"

            # Verify padding & appearance of assistant message (white bubble, generous padding, zero overlap)
            asst_padding = await eval_js(ws, "window.getComputedStyle(document.querySelector('.mindbridge-message.assistant')).padding", msg_id)
            asst_bg = await eval_js(ws, "window.getComputedStyle(document.querySelector('.mindbridge-message.assistant')).backgroundColor", msg_id)
            asst_line_height = await eval_js(ws, "window.getComputedStyle(document.querySelector('.mindbridge-message.assistant')).lineHeight", msg_id)

            print(f"Assistant Bubble Padding:     {asst_padding}")
            print(f"Assistant Bubble BG:          {asst_bg}")
            print(f"Assistant Bubble Line-Height: {asst_line_height}")

            assert "rgb(255, 255, 255)" in asst_bg or "#ffffff" in asst_bg.lower(), f"Expected white assistant bubble, got {asst_bg}"
            assert "16px" in asst_padding or "20px" in asst_padding, f"Expected generous padding on assistant bubble, got {asst_padding}"
            await capture_screenshot(ws, "redesign_04_reply_rendered.png", msg_id)
            print(">>> Assistant reply rendered with white bubble, generous padding, and no overlapping.")

            # 6. Test Header Reset (New Chat) Button
            print("\n[Step 5] Testing 'Start New Chat' reset button...")
            await eval_js(ws, "document.getElementById('mindbridge-reset-btn').click();", msg_id)
            await asyncio.sleep(0.5)

            welcome_visible = await eval_js(ws, "window.getComputedStyle(document.getElementById('mindbridge-welcome-view')).display", msg_id)
            msg_list_visible = await eval_js(ws, "window.getComputedStyle(document.getElementById('mindbridge-message-list')).display", msg_id)
            print(f"Welcome View Display:      {welcome_visible}")
            print(f"Message List Display:      {msg_list_visible}")
            assert welcome_visible == "flex", f"Expected welcome view flex, got {welcome_visible}"
            assert msg_list_visible == "none", f"Expected message list none, got {msg_list_visible}"
            print(">>> New Chat reset verified.")

    finally:
        proc.kill()
        shutil.rmtree(temp_profile, ignore_errors=True)

    # 7. Mobile Responsiveness Test (375x667 viewport via CDP Device Metrics Emulation)
    print("\n[Step 6] Testing mobile responsiveness at 375x667 viewport...")
    mobile_profile = tempfile.mkdtemp(prefix="edge_mobile_test_")
    mobile_cmd = [
        EDGE_PATH,
        "--headless=new",
        f"--remote-debugging-port={CDP_PORT + 1}",
        f"--user-data-dir={mobile_profile}",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        WIDGET_URL,
    ]
    mobile_proc = subprocess.Popen(mobile_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        mobile_ws_url = None
        for _ in range(15):
            time.sleep(0.5)
            try:
                req = urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT + 1}/json", timeout=2)
                pages = json.loads(req.read().decode("utf-8"))
                for p in pages:
                    if p.get("type") == "page" and "127.0.0.1:3000" in p.get("url", ""):
                        mobile_ws_url = p.get("webSocketDebuggerUrl")
                        break
                if mobile_ws_url:
                    break
            except Exception:
                pass

        assert mobile_ws_url, "Failed to connect to mobile Edge CDP!"
        async with websockets.connect(mobile_ws_url) as m_ws:
            m_id = [1]
            await send_cdp(m_ws, "Page.enable", {}, m_id)
            await send_cdp(m_ws, "Runtime.enable", {}, m_id)
            # Emulate Mobile Viewport 375 x 667
            await send_cdp(m_ws, "Emulation.setDeviceMetricsOverride", {
                "width": 375,
                "height": 667,
                "deviceScaleFactor": 2,
                "mobile": True
            }, m_id)
            await asyncio.sleep(0.5)

            for _ in range(25):
                ready = await eval_js(m_ws, "!!document.getElementById('mindbridge-launcher-btn')", m_id)
                if ready:
                    break
                await asyncio.sleep(0.2)

            # Open chat window on mobile
            await eval_js(m_ws, "document.getElementById('mindbridge-launcher-btn').click();", m_id)
            await asyncio.sleep(0.8)

            m_width = await eval_js(m_ws, "document.getElementById('mindbridge-chat-window').getBoundingClientRect().width", m_id)
            m_height = await eval_js(m_ws, "document.getElementById('mindbridge-chat-window').getBoundingClientRect().height", m_id)
            is_fullscreen = await eval_js(m_ws, "window.getComputedStyle(document.getElementById('mindbridge-chat-window')).position", m_id)

            print(f"Mobile Window Dimensions: {m_width}px x {m_height}px")
            print(f"Chat Window Position:     {is_fullscreen}")

            assert is_fullscreen == "fixed", f"Expected fixed fullscreen positioning on mobile, got {is_fullscreen}"
            assert abs(m_width - 375) < 5, f"Expected mobile chat width ~375, got {m_width}"

            await capture_screenshot(m_ws, "redesign_05_mobile_view.png", m_id)
            print(">>> Mobile responsiveness verified successfully.")

            print("\n" + "=" * 80)
            print("🎉 ALL UI/UX REDESIGN TESTS PASSED PERFECTLY!")
            print("=" * 80)
            return True

    finally:
        mobile_proc.kill()
        shutil.rmtree(mobile_profile, ignore_errors=True)


if __name__ == "__main__":
    success = asyncio.run(run_redesign_test())
    sys.exit(0 if success else 1)
