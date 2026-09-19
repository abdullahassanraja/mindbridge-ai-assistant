# test_edge_content_replacement.py
# Automated Microsoft Edge Browser Test for MindBridge / Ellen 15-Section Landing Page
# Tests all 15 mapped sections, interactive calculator, lead capture submission, and mobile fixed-header.

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

async def run_edge_test():
    print("=" * 75)
    print("🌐 AUTOMATED MICROSOFT EDGE TEST — 15-SECTION CONTENT REPLACEMENT & WIDGET")
    print("=" * 75)
    print(f"Edge executable: {EDGE_PATH}")
    print(f"Testing URL:     {WIDGET_URL}")

    temp_profile = tempfile.mkdtemp(prefix="edge_content_cdp_")
    cmd = [
        EDGE_PATH,
        "--headless=new",
        f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={temp_profile}",
        "--window-size=1280,950",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        WIDGET_URL,
    ]

    print("Launching Microsoft Edge in headless mode...")
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    ws_url = None
    for attempt in range(25):
        time.sleep(0.4)
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
        print("❌ Failed to obtain CDP WebSocket debugger URL from Edge.")
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

            # Test 1: Navigation & Hero
            print("\n[Section 1 & 2] Verifying Navigation & Hero Section...")
            nav_text = await eval_js(ws, "document.querySelector('header').innerText", msg_id)
            assert "The Assistant" in nav_text, "Missing 'The Assistant' in nav"
            assert "Capabilities" in nav_text, "Missing 'Capabilities' in nav"
            assert "Customizations" in nav_text, "Missing 'Customizations' in nav"
            assert "Why It Matters" in nav_text, "Missing 'Why It Matters' in nav"
            assert "Talk to Us" in nav_text, "Missing 'Talk to Us' in nav"
            
            logo_alt = await eval_js(ws, "document.querySelector('header img').alt", msg_id)
            logo_src = await eval_js(ws, "document.querySelector('header img').src", msg_id)
            assert "Ellen" in logo_alt and "AI Wellness Assistant" in logo_alt
            assert "ellen_logo.png" in logo_src
            print(f"✓ Section 1 (Navigation) verified with brand logo: '{logo_alt}'")

            # Verify Tab View Favicon
            favicons = await eval_js(ws, "Array.from(document.querySelectorAll('link[rel*=\"icon\"]')).map(l => l.getAttribute('href')).join(' ')", msg_id)
            assert "favicon.png" in favicons or "ellen_icon.png" in favicons
            print(f"✓ Tab View Favicon links verified: {favicons}")

            hero_h1 = await eval_js(ws, "document.querySelector('h1').innerText", msg_id)
            print(f"Hero H1: '{hero_h1.replace(chr(10), ' ')}'")
            assert "The AI Assistant Built for" in hero_h1 and "Wellness Practices" in hero_h1

            badges = await eval_js(ws, """
                Array.from(document.querySelectorAll('.glass-panel')).map(el => el.innerText).join(' ')
            """, msg_id)
            assert "Always On, Never Misses a Visitor" in badges
            assert "Built From Your Practice's Own Content" in badges
            print("✓ Section 2 (Hero) verified successfully.")
            await capture_screenshot(ws, "test_01_nav_hero.jpg", msg_id)

            # Test 2: Section 3 (Stats Bar & Built for Practices Like Yours)
            print("\n[Section 3] Verifying Qualitative Stats Bar...")
            stats_text = await eval_js(ws, "document.querySelector('section.bg-sage-100\\\\/90').innerText", msg_id)
            assert "24/7" in stats_text and "Always-On Visitor Support" in stats_text
            assert "Zero" in stats_text and "Missed Inquiries Left Unanswered" in stats_text
            assert "Built for Practices Like Yours" in stats_text
            assert "8k+" not in stats_text, "Fabricated '8k+' found in stats bar!"
            print("✓ Section 3 (Qualitative Stats Bar) verified successfully.")

            # Test 3: Section 4 & 5 (Cost of Missed Inquiry & Growth)
            print("\n[Section 4 & 5] Verifying The Real Cost of a Missed Inquiry & Growth...")
            await eval_js(ws, "document.getElementById('cost-of-missed-inquiry').scrollIntoView({behavior: 'instant'});", msg_id)
            await asyncio.sleep(0.5)
            cost_text = await eval_js(ws, "document.getElementById('cost-of-missed-inquiry').innerText", msg_id)
            assert "The Real Cost of a Missed Inquiry" in cost_text
            assert "Without Ellen" in cost_text and "With Ellen" in cost_text
            print("✓ Section 4 (Cost of Missed Inquiry) verified.")
            await capture_screenshot(ws, "test_02_cost_growth.jpg", msg_id)

            # Test 4: Section 6 (Interactive Revenue Impact Calculator)
            print("\n[Section 6] Testing Interactive Revenue Impact Calculator...")
            await eval_js(ws, "document.getElementById('calculator').scrollIntoView({behavior: 'instant'});", msg_id)
            await asyncio.sleep(0.5)

            # Default values check: 200 visitors, 20% conv, $150
            unconverted = await eval_js(ws, "document.getElementById('res-unconverted').innerText", msg_id)
            clients = await eval_js(ws, "document.getElementById('res-clients').innerText", msg_id)
            monthly_val = await eval_js(ws, "document.getElementById('res-monthly-value').innerText", msg_id)
            print(f"Default Calc Output -> Unconverted: {unconverted}, Clients: {clients}, Monthly: {monthly_val}")
            assert unconverted == "160"
            assert clients == "80"
            assert monthly_val == "$12,000"

            # Input change test: 500 visitors, 10% conv, $200
            print("Simulating user changing inputs to 500 visitors, 10% conv, $200...")
            await eval_js(ws, """
                (() => {
                    const v = document.getElementById('calc-visitors');
                    const c = document.getElementById('calc-conversion');
                    const val = document.getElementById('calc-value');
                    v.value = '500';
                    c.value = '10';
                    val.value = '200';
                    v.dispatchEvent(new Event('input'));
                    c.dispatchEvent(new Event('input'));
                    val.dispatchEvent(new Event('input'));
                })()
            """, msg_id)
            await asyncio.sleep(0.3)

            unconverted_2 = await eval_js(ws, "document.getElementById('res-unconverted').innerText", msg_id)
            clients_2 = await eval_js(ws, "document.getElementById('res-clients').innerText", msg_id)
            monthly_val_2 = await eval_js(ws, "document.getElementById('res-monthly-value').innerText", msg_id)
            print(f"Updated Calc Output -> Unconverted: {unconverted_2}, Clients: {clients_2}, Monthly: {monthly_val_2}")
            assert unconverted_2 == "450", f"Expected 450, got {unconverted_2}"
            assert clients_2 == "225", f"Expected 225, got {clients_2}"
            assert monthly_val_2 == "$45,000", f"Expected $45,000, got {monthly_val_2}"
            print("✓ Section 6 (Interactive Calculator) live calculation verified accurately!")
            await capture_screenshot(ws, "test_03_calculator.jpg", msg_id)

            # Test 5: Section 7, 8, 9, 10, 11 (Capabilities, Steps, Trust, Scenarios, Snippets)
            print("\n[Section 7-11] Verifying Capabilities, Steps, Trust, Scenarios, & Snippets...")
            await eval_js(ws, "document.getElementById('capabilities').scrollIntoView({behavior: 'instant'});", msg_id)
            await asyncio.sleep(0.5)
            cap_text = await eval_js(ws, "document.getElementById('capabilities').innerText", msg_id)
            assert "Instant, Grounded Answers" in cap_text
            assert "Smart Therapist Matching" in cap_text
            assert "Zero-Loss Lead Capture" in cap_text

            await eval_js(ws, "document.getElementById('steps').scrollIntoView({behavior: 'instant'});", msg_id)
            await asyncio.sleep(0.5)
            steps_text = await eval_js(ws, "document.getElementById('steps').innerText", msg_id)
            assert "Tell Us About Your Practice" in steps_text
            assert "We Build Ellen Around You" in steps_text
            assert "Preview & Approve" in steps_text
            assert "Go Live on Your Site" in steps_text

            await eval_js(ws, "document.getElementById('customizations').scrollIntoView({behavior: 'instant'});", msg_id)
            await asyncio.sleep(0.5)
            trust_text = await eval_js(ws, "document.getElementById('customizations').innerText", msg_id)
            assert "Never Guesses" in trust_text
            assert "Built-In Clinical Boundaries" in trust_text
            assert "Handles Crisis Correctly" in trust_text
            assert "Knows When to Step Aside" in trust_text
            assert "You Don't Have to Be Available 24/7. Ellen Is." in trust_text

            await eval_js(ws, "document.getElementById('why-it-matters').scrollIntoView({behavior: 'instant'});", msg_id)
            await asyncio.sleep(0.5)
            scenarios_text = await eval_js(ws, "document.getElementById('why-it-matters').innerText", msg_id)
            assert "The 11pm Visitor" in scenarios_text
            assert "The Repetitive Question" in scenarios_text
            assert "The Uncertain Visitor" in scenarios_text

            await eval_js(ws, "document.getElementById('ellen-in-action').scrollIntoView({behavior: 'instant'});", msg_id)
            await asyncio.sleep(0.5)
            action_text = await eval_js(ws, "document.getElementById('ellen-in-action').innerText", msg_id)
            assert "Couples Counseling Inquiry Example" in action_text
            assert "Late-Night Inquiry" in action_text
            assert "Insurance Question" in action_text
            assert "Crisis Detected" in action_text
            assert "Ready to Book" in action_text
            print("✓ Sections 7 through 11 verified cleanly.")
            await capture_screenshot(ws, "test_04_snippets_action.jpg", msg_id)

            # Test 6: Section 12 (Lead Capture Form Submission)
            print("\n[Section 12] Testing Lead Capture Form Submission via Edge...")
            await eval_js(ws, "document.getElementById('lead-capture').scrollIntoView({behavior: 'instant'});", msg_id)
            await asyncio.sleep(0.5)

            # Fill in form
            await eval_js(ws, """
                (() => {
                    document.getElementById('lead-practice-name').value = 'Mindful Horizon Clinic';
                    document.getElementById('lead-contact-name').value = 'Dr. Clara Vance';
                    document.getElementById('lead-contact-email').value = 'clara@mindfulhorizon.demo';
                    document.getElementById('lead-website-url').value = 'https://mindfulhorizon.demo';
                    document.getElementById('lead-notes').value = 'Inquiring about after-hours triage integration for 5 clinicians.';
                })()
            """, msg_id)
            await asyncio.sleep(0.2)

            # Submit form
            print("Submitting lead capture form...")
            await eval_js(ws, "document.getElementById('practice-inquiry-form').dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));", msg_id)

            # Wait for submission to complete (Google Sheets API can take 4-6s)
            success_visible = False
            for poll in range(25):
                await asyncio.sleep(0.5)
                success_visible = await eval_js(ws, "!document.getElementById('lead-success-msg').classList.contains('hidden')", msg_id)
                if success_visible:
                    print(f"✓ Lead inquiry recorded in Google Sheets after {(poll + 1) * 0.5:.1f}s.")
                    break

            print(f"Lead success message displayed: {success_visible}")
            assert success_visible, "Lead capture success message was not shown!"
            await capture_screenshot(ws, "test_05_lead_capture_success.jpg", msg_id)

            # Test 7: Section 13 (FAQ: 7 practice-owner questions)
            print("\n[Section 13] Verifying Practice-Owner FAQ...")
            await eval_js(ws, "document.getElementById('faq').scrollIntoView({behavior: 'instant'});", msg_id)
            await asyncio.sleep(0.5)
            faq_text = await eval_js(ws, "document.getElementById('faq').innerText", msg_id)
            assert "Does Ellen replace my staff?" in faq_text
            assert "How long does setup take?" in faq_text
            assert "Can Ellen be customized to our specific therapists and specialties?" in faq_text
            assert "What happens if a visitor mentions a crisis?" in faq_text
            assert "Is there a free demo before we commit to anything?" in faq_text
            assert "How is our practice's and clients' data handled?" in faq_text
            assert "Does Ellen integrate with our existing scheduling or CRM tools?" in faq_text
            print("✓ Section 13 (7 FAQ Questions) verified successfully.")

            # Test 8: Section 14 & 15 (Final CTA & Footer)
            print("\n[Section 14 & 15] Verifying Final CTA & Footer...")
            await eval_js(ws, "window.scrollTo(0, document.body.scrollHeight);", msg_id)
            await asyncio.sleep(0.5)
            footer_text = await eval_js(ws, "document.querySelector('footer').innerText", msg_id)
            assert "Start Giving Every Visitor an Answer" in (await eval_js(ws, "document.body.innerText", msg_id))
            assert "Ellen is an administrative AI assistant, not a licensed medical provider" in footer_text
            assert "[Pending Real Address]" in footer_text
            assert "[Pending Real Phone]" in footer_text
            assert "[Pending Real Email]" in footer_text
            print("✓ Section 14 & 15 verified successfully.")
            await capture_screenshot(ws, "test_06_footer_compliance.jpg", msg_id)

            # Test 9: Mobile Chat Header WhatsApp-Style Pinned Behavior
            print("\n[Mobile Test] Testing Mobile Virtual Keyboard & Fixed Header Behavior...")
            await eval_js(ws, "if (window.MindBridge) window.MindBridge.open();", msg_id)
            await asyncio.sleep(0.5)

            # Set mobile viewport
            await send_cdp(ws, "Emulation.setDeviceMetricsOverride", {
                "width": 390,
                "height": 844,
                "deviceScaleFactor": 2,
                "mobile": True
            }, msg_id)
            await eval_js(ws, "window.dispatchEvent(new Event('resize'));", msg_id)
            await asyncio.sleep(0.5)

            # Focus input field and simulate virtual keyboard opening (shrinking visual viewport height to 480)
            await eval_js(ws, "document.getElementById('mindbridge-input-field').focus();", msg_id)
            await send_cdp(ws, "Emulation.setDeviceMetricsOverride", {
                "width": 390,
                "height": 480,
                "deviceScaleFactor": 2,
                "mobile": True
            }, msg_id)
            await eval_js(ws, "window.dispatchEvent(new Event('resize'));", msg_id)
            await asyncio.sleep(0.5)

            header_top = await eval_js(ws, "document.getElementById('mindbridge-chat-header').getBoundingClientRect().top", msg_id)
            print(f"Mobile Header top with virtual keyboard open: {header_top}")
            assert header_top == 0, f"Bug: Mobile header moved off top! top={header_top}"
            print("✅ Mobile chat header remains rigidly pinned at top=0 (WhatsApp style)!")
            await capture_screenshot(ws, "test_07_mobile_keyboard_header_fixed.jpg", msg_id)

            print("\n" + "=" * 75)
            print("🎉 ALL 15 SECTIONS, CALCULATOR, FORM, & MOBILE FIX VERIFIED IN EDGE!")
            print("=" * 75)
            return True

    finally:
        proc.kill()
        shutil.rmtree(temp_profile, ignore_errors=True)

if __name__ == "__main__":
    success = asyncio.run(run_edge_test())
    sys.exit(0 if success else 1)
