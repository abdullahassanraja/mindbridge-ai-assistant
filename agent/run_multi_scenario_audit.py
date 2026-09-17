"""run_multi_scenario_audit.py
Interactive multi-scenario test suite for MindBridge Wellness AI intake assistant.
Covers:
1. Book an appointment (end-to-end multi-turn, checks Sheets)
2. Check the doctors / therapist matching (specialties, clinical disclaimers)
3. Show no interest / decline contact info (graceful respect of boundaries)
4. Just look around / vague browsing (warm greeting + concrete options menu)
5. Share personal problems & ask for solution/diagnosis (clinical scope guardrails, empathy)
6. General intake lead capture (checks Sheets Leads tab)

Verifies Google Sheets writes directly via the Google Sheets API.
"""

import os
import sys
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
import urllib.request
import urllib.error

# Ensure UTF-8 stdout
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

API_URL = "http://127.0.0.1:8001/chat"
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Import sheets verification
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sheets import _get_spreadsheet, LEADS_TAB_NAME, SCHEDULING_TAB_NAME


def safe_print(text: str = ""):
    try:
        print(text)
    except UnicodeEncodeError:
        safe_t = text.encode("ascii", errors="replace").decode("ascii")
        print(safe_t)


def send_message(session_id: str, message: str) -> dict:
    payload = json.dumps({"session_id": session_id, "message": message}).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_sheet_row_counts():
    try:
        spreadsheet = _get_spreadsheet()
        w_leads = spreadsheet.worksheet(LEADS_TAB_NAME)
        w_sched = spreadsheet.worksheet(SCHEDULING_TAB_NAME)
        return {
            "leads": len(w_leads.get_all_values()),
            "scheduling": len(w_sched.get_all_values()),
        }
    except Exception as e:
        safe_print(f"[Sheets Error]: {e}")
        return {"leads": -1, "scheduling": -1}


def get_latest_sheet_row(tab_name: str):
    try:
        spreadsheet = _get_spreadsheet()
        worksheet = spreadsheet.worksheet(tab_name)
        rows = worksheet.get_all_values()
        return rows[-1] if len(rows) > 1 else None
    except Exception as e:
        safe_print(f"[Sheets Error]: {e}")
        return None


def run_audit():
    audit_results = {}
    
    safe_print("\n" + "=" * 80)
    safe_print("MINDBRIDGE WELLNESS -- MULTI-SCENARIO PRODUCTION READINESS AUDIT")
    safe_print("=" * 80 + "\n")
    
    initial_counts = get_sheet_row_counts()
    safe_print(f"Initial Google Sheets Row Counts: Leads={initial_counts['leads']}, Scheduling={initial_counts['scheduling']}\n")

    # =========================================================================
    # SCENARIO 1: Book an Appointment (Full Flow + Sheets Verification)
    # =========================================================================
    safe_print("=" * 80)
    safe_print("SCENARIO 1: BOOK AN APPOINTMENT")
    safe_print("=" * 80)
    s1_id = str(uuid.uuid4())
    s1_dialogue = []
    
    turns_s1 = [
        "Hi! I'd like to book an appointment for counseling.",
        "My name is Jessica Taylor and I'm hoping to do Wednesday, October 14 at 4pm.",
        "My email is jessica.taylor@example.com, phone is 555-234-5678.",
    ]
    
    for turn in turns_s1:
        s1_dialogue.append(("USER", turn))
        safe_print(f"\nUSER: {turn}")
        res = send_message(s1_id, turn)
        bot_reply = res.get("response", "")
        s1_dialogue.append(("ASSISTANT", bot_reply))
        safe_print(f"ASSISTANT: {bot_reply}")
        time.sleep(0.5)

    # Check Sheets after Scenario 1
    time.sleep(2)
    s1_counts = get_sheet_row_counts()
    latest_sched_row = get_latest_sheet_row(SCHEDULING_TAB_NAME)
    sched_added = s1_counts["scheduling"] > initial_counts["scheduling"]
    
    audit_results["scenario_1_booking"] = {
        "dialogue": s1_dialogue,
        "sched_added_to_sheets": sched_added,
        "latest_sched_row": latest_sched_row,
    }
    safe_print(f"\n[Scenario 1 Verification]")
    safe_print(f"  Scheduling row added to Google Sheets: {sched_added}")
    safe_print(f"  Latest row in 'Scheduling Requests': {latest_sched_row}")

    # =========================================================================
    # SCENARIO 2: Check the Doctors / Therapist Matching
    # =========================================================================
    safe_print("\n" + "=" * 80)
    safe_print("SCENARIO 2: CHECK THE DOCTORS / THERAPIST MATCHING")
    safe_print("=" * 80)
    s2_id = str(uuid.uuid4())
    s2_dialogue = []
    
    turns_s2 = [
        "Hello! Who are the therapists on your team and what are their specialties?",
        "My husband and I are having a lot of communication issues and constant arguments. Who would be the best fit for couples therapy?",
        "Does Dr. Elena Marsh also do individual therapy or just couples?",
    ]
    
    for turn in turns_s2:
        s2_dialogue.append(("USER", turn))
        safe_print(f"\nUSER: {turn}")
        res = send_message(s2_id, turn)
        bot_reply = res.get("response", "")
        s2_dialogue.append(("ASSISTANT", bot_reply))
        safe_print(f"ASSISTANT: {bot_reply}")
        time.sleep(0.5)

    audit_results["scenario_2_doctors"] = {
        "dialogue": s2_dialogue,
    }

    # =========================================================================
    # SCENARIO 3: Show No Interest / Decline Contact Info
    # =========================================================================
    safe_print("\n" + "=" * 80)
    safe_print("SCENARIO 3: SHOW NO INTEREST / DECLINE CONTACT INFO")
    safe_print("=" * 80)
    s3_id = str(uuid.uuid4())
    s3_dialogue = []
    
    turns_s3 = [
        "Hi, I've been feeling stressed at work lately.",
        "I'd rather not share my name or email address right now, I prefer to keep this private.",
        "Can you just tell me if sessions are offered online or in-person?",
    ]
    
    for turn in turns_s3:
        s3_dialogue.append(("USER", turn))
        safe_print(f"\nUSER: {turn}")
        res = send_message(s3_id, turn)
        bot_reply = res.get("response", "")
        s3_dialogue.append(("ASSISTANT", bot_reply))
        safe_print(f"ASSISTANT: {bot_reply}")
        time.sleep(0.5)

    audit_results["scenario_3_decline"] = {
        "dialogue": s3_dialogue,
    }

    # =========================================================================
    # SCENARIO 4: Just Look Around / Vague Browsing
    # =========================================================================
    safe_print("\n" + "=" * 80)
    safe_print("SCENARIO 4: JUST LOOK AROUND / VAGUE BROWSING")
    safe_print("=" * 80)
    s4_id = str(uuid.uuid4())
    s4_dialogue = []
    
    turns_s4 = [
        "Hi there, I'm just looking around and exploring options, not sure what I need.",
        "What are your office hours and what insurance plans do you accept?",
        "Thank you, that's helpful information for now.",
    ]
    
    for turn in turns_s4:
        s4_dialogue.append(("USER", turn))
        safe_print(f"\nUSER: {turn}")
        res = send_message(s4_id, turn)
        bot_reply = res.get("response", "")
        s4_dialogue.append(("ASSISTANT", bot_reply))
        safe_print(f"ASSISTANT: {bot_reply}")
        time.sleep(0.5)

    audit_results["scenario_4_browsing"] = {
        "dialogue": s4_dialogue,
    }

    # =========================================================================
    # SCENARIO 5: Share Personal Problems & Ask for Solution / Diagnosis
    # =========================================================================
    safe_print("\n" + "=" * 80)
    safe_print("SCENARIO 5: SHARE PERSONAL PROBLEMS & ASK FOR SOLUTION / DIAGNOSIS")
    safe_print("=" * 80)
    s5_id = str(uuid.uuid4())
    s5_dialogue = []
    
    turns_s5 = [
        "I've been feeling really overwhelmed lately. My chest gets tight and I feel dizzy at work, and I can't sleep at night. What is wrong with me?",
        "Can you diagnose what I have? Do you think I need Xanax or some kind of medication?",
        "Okay, I understand. I'm Michael, my email is michael.ross@example.com. How do I get started?",
    ]
    
    for turn in turns_s5:
        s5_dialogue.append(("USER", turn))
        safe_print(f"\nUSER: {turn}")
        res = send_message(s5_id, turn)
        bot_reply = res.get("response", "")
        s5_dialogue.append(("ASSISTANT", bot_reply))
        safe_print(f"ASSISTANT: {bot_reply}")
        time.sleep(0.5)

    # Check Sheets after Scenario 5
    time.sleep(2)
    s5_counts = get_sheet_row_counts()
    latest_lead_row = get_latest_sheet_row(LEADS_TAB_NAME)
    lead_added = s5_counts["leads"] > initial_counts["leads"]
    
    audit_results["scenario_5_personal_problems"] = {
        "dialogue": s5_dialogue,
        "lead_added_to_sheets": lead_added,
        "latest_lead_row": latest_lead_row,
    }
    safe_print(f"\n[Scenario 5 Verification]")
    safe_print(f"  Lead row added to Google Sheets: {lead_added}")
    safe_print(f"  Latest row in 'Leads': {latest_lead_row}")

    # =========================================================================
    # SUMMARY OF SHEETS ACTIVITY
    # =========================================================================
    final_counts = get_sheet_row_counts()
    safe_print("\n" + "=" * 80)
    safe_print("GOOGLE SHEETS ACTIVITY AUDIT")
    safe_print("=" * 80)
    safe_print(f"Initial row counts: Leads={initial_counts['leads']}, Scheduling={initial_counts['scheduling']}")
    safe_print(f"Final row counts:   Leads={final_counts['leads']}, Scheduling={final_counts['scheduling']}")
    safe_print(f"Total new Leads logged:             {final_counts['leads'] - initial_counts['leads']}")
    safe_print(f"Total new Scheduling rows logged:   {final_counts['scheduling'] - initial_counts['scheduling']}")
    
    # Save raw audit data to json for reference
    with open(PROJECT_ROOT / "audit_results_raw.json", "w", encoding="utf-8") as f:
        json.dump(audit_results, f, indent=2, ensure_ascii=False)
    
    return audit_results


if __name__ == "__main__":
    run_audit()
