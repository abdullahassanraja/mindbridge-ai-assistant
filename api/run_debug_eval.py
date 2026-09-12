# run_debug_eval.py
import os
import sys

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient
import main

client = TestClient(main.app)

test_messages = [
    "What are your office hours?",
    "My partner and I keep fighting, can you help?",
    "I want to talk to a real person",
]

session_id = "test-session-investigation-123"

print("=" * 70)
print("STARTING DEBUG INVESTIGATION EVALUATION (3 DISTINCT MESSAGES)")
print("=" * 70)

for i, msg in enumerate(test_messages, 1):
    print(f"\n=======================================================")
    print(f"TEST TURN {i}: '{msg}'")
    print(f"=======================================================")
    resp = client.post("/chat", json={"session_id": session_id, "message": msg})
    data = resp.json()
    print(f"\n[FINAL RETURNED RESPONSE {i}]:")
    print(data["response"])

print("\n" + "=" * 70)
print("EVALUATION FINISHED")
print("=" * 70)
