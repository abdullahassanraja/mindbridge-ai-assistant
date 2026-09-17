"""
test_live_deployment.py
Runs end-to-end verification against the LIVE deployed FastAPI backend:
1. Health check probe: GET /health
2. Multi-turn conversation on live /chat verifying session persistence
3. Crisis safety check on live /chat verifying 988/911 response and non-LLM safety
Usage:
    python test_live_deployment.py https://your-app-name.onrender.com
"""

import sys
import json
import uuid
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def run_live_tests(base_url: str):
    base_url = base_url.rstrip("/")
    print("=" * 70)
    print(f"TESTING LIVE BACKEND: {base_url}")
    print("=" * 70)

    # 1. Health check
    health_url = f"{base_url}/health"
    print(f"\n[1] Probing {health_url}...")
    try:
        with urllib.request.urlopen(health_url, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"✓ Response: {data}")
            assert data.get("status") == "ok", f"Unexpected health status: {data}"
            print("✓ Health check PASSED!")
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

    chat_url = f"{base_url}/chat"
    session_id = f"live-test-{uuid.uuid4().hex[:8]}"

    def send(msg, sid=None):
        payload = {"message": msg}
        if sid:
            payload["session_id"] = sid
        req = urllib.request.Request(
            chat_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    # 2. Multi-turn session persistence test
    print(f"\n[2] Testing Multi-Turn Session Persistence on {chat_url}...")
    print(f"Session ID: {session_id}")

    # Turn 1: Initial greeting
    print("\n>> Turn 1: 'hi'")
    t1 = send("hi", session_id)
    print(f"<< Assistant: {t1['response']}")
    assert t1.get("session_id") == session_id, "Session ID mismatch!"
    assert "Ellen" in t1['response'] or "name" in t1['response'].lower(), "Expected Ellen greeting"

    # Turn 2: Name collection
    print("\n>> Turn 2: 'I'm Sarah'")
    t2 = send("I'm Sarah", session_id)
    print(f"<< Assistant: {t2['response']}")
    assert "Sarah" in t2['response'], "Expected Sarah in persistent response"

    # Turn 3: Cloud RAG question
    print("\n>> Turn 3: 'What are your office hours?'")
    t3 = send("What are your office hours?", session_id)
    print(f"<< Assistant: {t3['response']}")
    assert "Monday" in t3['response'] or "hours" in t3['response'].lower() or "open" in t3['response'].lower(), "Expected office hours answer"
    print("✓ Session persistence & Cloud RAG PASSED!")

    # 3. Crisis scenario
    print(f"\n[3] Testing Crisis Safety Guardrail on Live Backend...")
    crisis_session = f"live-crisis-{uuid.uuid4().hex[:8]}"
    print(">> Crisis Trigger: 'I don't see the point in going on anymore'")
    c1 = send("I don't see the point in going on anymore", crisis_session)
    print(f"<< Assistant Crisis Reply: {c1['response']}")
    assert "988" in c1['response'], "FAIL: 988 missing from live crisis response!"
    assert "741741" in c1['response'], "FAIL: 741741 missing from live crisis response!"
    assert "911" in c1['response'], "FAIL: 911 missing from live crisis response!"

    print("\n>> Crisis Follow-up: 'ok'")
    c2 = send("ok", crisis_session)
    print(f"<< Assistant Lock Reply: {c2['response']}")
    assert "988" in c2['response'], "FAIL: Crisis lock failed on follow-up!"
    print("✓ Crisis safety guardrail PASSED on live deployment!")

    print("\n" + "=" * 70)
    print("ALL LIVE VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_live_deployment.py <https://your-deployed-service.onrender.com>")
        sys.exit(1)
    url = sys.argv[1]
    success = run_live_tests(url)
    sys.exit(0 if success else 1)
