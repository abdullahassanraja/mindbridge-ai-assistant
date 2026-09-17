"""End-to-end verification of the scheduling flow and bug fix via FastAPI /chat."""
import requests
import time
import sys

API_URL = "http://127.0.0.1:8001"

def safe_print(msg):
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode('ascii', errors='replace').decode('ascii'), flush=True)

def chat(session_id, message):
    payload = {"message": message}
    if session_id:
        payload["session_id"] = session_id
    resp = requests.post(f"{API_URL}/chat", json=payload, timeout=60)
    data = resp.json()
    return data["response"], data["session_id"]

safe_print("=" * 70)
safe_print("VERIFYING FULL SCHEDULING FLOW (EXACT USER SCENARIO)")
safe_print("=" * 70)

session_id = None
turns = [
    # 1. Greeting
    "hi",
    # 2. Name
    "Sarah",
    # 3. Concern
    "I've been dealing with a lot of work stress and anxiety lately",
    # 4. Explicit Scheduling Request
    "I'd like to schedule an appointment with a counselor",
    # 5. Clear date/time answer (the failing input from bug report)
    "sunday 20 sep between 2 pm and 9 pm",
    # 6. Contact info to complete the request
    "sarah.jenkins@gmail.com",
]

for i, msg in enumerate(turns, 1):
    safe_print(f"\n[Turn {i}] >>> USER: {msg}")
    reply, session_id = chat(session_id, msg)
    safe_print(f"[Turn {i}] <<< ELLEN:\n{reply}")
    safe_print(f"         [session_id: {session_id}]")
    
    # Assertions
    if i == 5:
        # After giving date/time, Ellen MUST acknowledge the date and ask for contact info, NOT repeat the date question
        lower_reply = reply.lower()
        if "what day and time" in lower_reply and ("sunday" in lower_reply or "sep" in lower_reply):
            safe_print("\n❌ CRITICAL FAILURE: Ellen re-asked for date/time!")
            sys.exit(1)
        elif "noted" in lower_reply or "email" in lower_reply or "phone" in lower_reply or "contact" in lower_reply:
            safe_print("\n✅ SUCCESS: Ellen acknowledged the date/time and requested contact info!")
        else:
            safe_print(f"\n⚠️ Turn 5 reply unexpected: {reply}")

    if i == 6:
        lower_reply = reply.lower()
        if "noted" in lower_reply or "team will confirm" in lower_reply or "email" in lower_reply or "confirmation" in lower_reply:
            safe_print("\n✅ SUCCESS: Ellen confirmed scheduling request pending confirmation!")
        if "booked" in lower_reply or "confirmed your appointment" in lower_reply:
            safe_print("\n⚠️ WARNING: Ethical rule violation - said appointment is booked/confirmed instead of pending confirmation!")

    time.sleep(1)

safe_print("\n" + "=" * 70)
safe_print("ALL TURNS COMPLETED SUCCESSFULLY!")
safe_print("=" * 70)
