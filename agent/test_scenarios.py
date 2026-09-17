# test_scenarios.py
# Verification of all 4 conversational flows against the live API

import json
import re
import sys
import time
import urllib.request
import uuid

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import os

API_URL = f"http://127.0.0.1:{os.environ.get('PORT', '8001')}/chat"

def send_chat(session_id: str, message: str) -> str:
    time.sleep(1.5)  # brief pause to pace Groq API rate limits
    req = urllib.request.Request(
        API_URL,
        data=json.dumps({"session_id": session_id, "message": message}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data.get("response", "")

def check_formatting(text: str, label: str):
    has_md_asterisks = "**" in text or bool(re.search(r'(?<!\*)\*(?!\*)', text))
    has_md_hashes = bool(re.search(r'^\s*#{1,6}\s', text, re.MULTILINE))
    has_em_dash = "—" in text
    has_corporate_filler = any(phrase in text.lower() for phrase in [
        "based on mindbridge wellness",
        "we are committed to",
        "our team is available to confirm",
    ])
    
    print(f"[{label}] Checks:")
    print(f"  - Markdown asterisks: {'FAILED (found **)' if has_md_asterisks else 'PASSED (none)'}")
    print(f"  - Markdown hashes:    {'FAILED (found #)' if has_md_hashes else 'PASSED (none)'}")
    print(f"  - Em dashes:          {'FAILED (found —)' if has_em_dash else 'PASSED (none)'}")
    print(f"  - Corporate filler:   {'FAILED (found)' if has_corporate_filler else 'PASSED (none)'}")
    print(f"  - Length (chars):     {len(text)}")
    print(f"  - Clean preview:      {text[:120]}")
    print()

def run_all_tests():
    print("==================================================")
    print("SCENARIO 1: Happy Path Intake")
    print("==================================================")
    s1 = str(uuid.uuid4())
    
    r1_1 = send_chat(s1, "Hi there")
    print(f"User: Hi there\nAssistant:\n{r1_1}\n")
    check_formatting(r1_1, "S1.1 Welcome")

    r1_2 = send_chat(s1, "Sarah")
    print(f"User: Sarah\nAssistant:\n{r1_2}\n")
    check_formatting(r1_2, "S1.2 Name")

    r1_3 = send_chat(s1, "I've been dealing with a lot of anxiety and stress at work lately")
    print(f"User: I've been dealing with a lot of anxiety and stress at work lately\nAssistant:\n{r1_3}\n")
    check_formatting(r1_3, "S1.3 Concern")

    r1_4 = send_chat(s1, "sarah.m@example.com")
    print(f"User: sarah.m@example.com\nAssistant:\n{r1_4}\n")
    check_formatting(r1_4, "S1.4 Contact")

    print("==================================================")
    print("SCENARIO 2: Early Volunteered Contact Info")
    print("==================================================")
    s2 = str(uuid.uuid4())
    
    r2_1 = send_chat(s2, "Hi, I'm struggling with conflict with my partner, you can email me at alex@example.com")
    print(f"User: Hi, I'm struggling with conflict with my partner, you can email me at alex@example.com\nAssistant:\n{r2_1}\n")
    check_formatting(r2_1, "S2.1 Early Contact")

    r2_2 = send_chat(s2, "My name is Alex Rivera")
    print(f"User: My name is Alex Rivera\nAssistant:\n{r2_2}\n")
    check_formatting(r2_2, "S2.2 Name")

    print("==================================================")
    print("SCENARIO 3: Contact Info Declined")
    print("==================================================")
    s3 = str(uuid.uuid4())
    
    r3_1 = send_chat(s3, "Hello")
    print(f"User: Hello\nAssistant:\n{r3_1}\n")
    check_formatting(r3_1, "S3.1 Greeting")

    r3_2 = send_chat(s3, "David")
    print(f"User: David\nAssistant:\n{r3_2}\n")
    check_formatting(r3_2, "S3.2 Name")

    r3_3 = send_chat(s3, "I'm dealing with grief after losing my father")
    print(f"User: I'm dealing with grief after losing my father\nAssistant:\n{r3_3}\n")
    check_formatting(r3_3, "S3.3 Concern")

    r3_4 = send_chat(s3, "I'd rather not share my contact info right now")
    print(f"User: I'd rather not share my contact info right now\nAssistant:\n{r3_4}\n")
    check_formatting(r3_4, "S3.4 Declined")

    print("==================================================")
    print("SCENARIO 4: FAQ / Practice Information")
    print("==================================================")
    s4 = str(uuid.uuid4())
    
    r4_1 = send_chat(s4, "Do you accept insurance and what are your fees?")
    print(f"User: Do you accept insurance and what are your fees?\nAssistant:\n{r4_1}\n")
    check_formatting(r4_1, "S4.1 Insurance & Fees FAQ")

    r4_2 = send_chat(s4, "What counseling services do you offer?")
    print(f"User: What counseling services do you offer?\nAssistant:\n{r4_2}\n")
    check_formatting(r4_2, "S4.2 Services FAQ")

if __name__ == "__main__":
    run_all_tests()
