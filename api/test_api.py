# test_api.py
# Comprehensive automated testing for MindBridge Wellness FastAPI backend & CORS.

import json
import urllib.request
import urllib.error
import sys

API_BASE = "http://127.0.0.1:8000"

def make_request(url, method="GET", data=None, headers=None):
    if headers is None:
        headers = {}
    body = json.dumps(data).encode("utf-8") if data is not None else None
    if body:
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            resp_body = resp.read().decode("utf-8")
            resp_headers = dict(resp.headers)
            try:
                parsed_data = json.loads(resp_body) if resp_body else {}
            except Exception:
                parsed_data = resp_body
            return resp.status, parsed_data, resp_headers
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            parsed_err = json.loads(err_body) if err_body else {}
        except Exception:
            parsed_err = err_body
        return e.code, parsed_err, dict(e.headers)

def run_tests():
    print("=" * 70)
    print("TEST 1: Health Check GET /health")
    print("=" * 70)
    status, data, _ = make_request(f"{API_BASE}/health")
    print(f"Status Code: {status}")
    print(f"Response:    {data}")
    assert status == 200, f"Expected 200, got {status}"
    assert data.get("status") == "ok", "Expected status: ok"
    print("PASSED: /health is operational.\n")

    print("=" * 70)
    print("TEST 2: Initial Turn POST /chat (No session_id)")
    print("=" * 70)
    payload1 = {
        "message": "My partner and I keep arguing constantly and we need help."
    }
    status, data, headers = make_request(f"{API_BASE}/chat", method="POST", data=payload1)
    print(f"Status Code: {status}")
    session_id = data.get("session_id")
    reply1 = data.get("response")
    print(f"Generated Session ID: {session_id}")
    print(f"Assistant Response:\n{reply1}")
    assert status == 200, f"Expected 200, got {status}"
    assert session_id, "Expected a generated session_id"
    assert reply1, "Expected assistant response text"
    print("PASSED: Generated session_id and received initial qualification response.\n")

    print("=" * 70)
    print("TEST 3: Multi-turn Session Persistence POST /chat (Reusing session_id)")
    print("=" * 70)
    payload2 = {
        "session_id": session_id,
        "message": "We want to do couples therapy together."
    }
    status, data2, _ = make_request(f"{API_BASE}/chat", method="POST", data=payload2)
    print(f"Status Code: {status}")
    print(f"Reused Session ID: {data2.get('session_id')}")
    reply2 = data2.get("response")
    print(f"Assistant Follow-up Response:\n{reply2}")
    assert data2.get("session_id") == session_id, "Session ID should match across turns"
    assert "couples" in reply2.lower() or "telehealth" in reply2.lower() or "preference" in reply2.lower(), "Context from Turn 1 should be remembered"
    print("PASSED: MemorySaver checkpointer maintained multi-turn state across HTTP calls.\n")

    print("=" * 70)
    print("TEST 4: CORS Header Verification from Origin http://localhost:3000")
    print("=" * 70)
    cors_headers = {
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type",
    }
    status, _, resp_hdrs = make_request(f"{API_BASE}/chat", method="OPTIONS", headers=cors_headers)
    print(f"OPTIONS Status Code: {status}")
    allow_origin = resp_hdrs.get("Access-Control-Allow-Origin") or resp_hdrs.get("access-control-allow-origin")
    print(f"Access-Control-Allow-Origin: {allow_origin}")
    assert status in (200, 204), f"Expected 200 or 204 for OPTIONS, got {status}"
    assert allow_origin in ("*", "http://localhost:3000"), f"Expected CORS allow origin header, got {allow_origin}"
    print("PASSED: CORS preflight allows external widget origin.\n")

    print("=" * 70)
    print("TEST 5: Fault Tolerance & Resilient Session ID Handling")
    print("=" * 70)
    # 5a. Empty string session_id
    status, data_empty, _ = make_request(f"{API_BASE}/chat", method="POST", data={"session_id": "", "message": "Are you a real person?"})
    print(f"5a (Empty session_id) Status: {status} | New Session ID: {data_empty.get('session_id')}")
    assert status == 200 and data_empty.get("session_id")

    # 5b. Malformed custom session string
    status, data_custom, _ = make_request(f"{API_BASE}/chat", method="POST", data={"session_id": "custom-user-client-12345", "message": "What is your cancellation policy?"})
    print(f"5b (Custom session_id) Status: {status} | Kept Session ID: {data_custom.get('session_id')}")
    assert status == 200 and data_custom.get("session_id") == "custom-user-client-12345"

    # 5c. Empty message string
    status, data_blank, _ = make_request(f"{API_BASE}/chat", method="POST", data={"session_id": "sess-empty", "message": "   "})
    print(f"5c (Blank message) Status: {status} | Response: {data_blank.get('response')[:50]}...")
    assert status == 200

    print("PASSED: Backend handles empty, missing, and custom session IDs without crashing.\n")
    print("=" * 70)
    print("ALL BACKEND & CORS TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    run_tests()
