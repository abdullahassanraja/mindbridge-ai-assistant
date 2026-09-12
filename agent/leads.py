# leads.py
# Lead capture and human handoff notification logging for MindBridge Wellness.

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

LEADS_FILE = Path(__file__).resolve().parent / "leads.json"
HANDOFFS_FILE = Path(__file__).resolve().parent / "handoffs.json"


def send_lead_email(
    name: Optional[str],
    contact: Optional[str],
    need: Optional[str],
    suggested_therapist: Optional[str] = None,
    qualification_info: Optional[Dict[str, Any]] = None,
) -> bool:
    """Format and send a lead notification.
    
    Currently stubs email dispatch by printing a formatted lead summary
    and appending the record to leads.json. Structured for simple replacement
    with an SMTP or email provider (SendGrid, Postmark, Resend, etc.).
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    lead_record = {
        "timestamp": timestamp,
        "name": name or "Anonymous Visitor",
        "contact": contact or "Not provided",
        "stated_need": need or "General inquiry",
        "suggested_therapist": suggested_therapist or "None assigned yet",
        "qualification_details": qualification_info or {},
    }

    # 1. Console notification banner
    print("\n" + "=" * 60)
    print("📢 [NEW LEAD NOTIFICATION]")
    print(f"Time:       {timestamp}")
    print(f"Name:       {lead_record['name']}")
    print(f"Contact:    {lead_record['contact']}")
    print(f"Need:       {lead_record['stated_need']}")
    print(f"Therapist:  {lead_record['suggested_therapist']}")
    if qualification_info:
        for k, v in qualification_info.items():
            if k not in ("name", "contact"):
                print(f"  • {k}: {v}")
    print("=" * 60 + "\n")

    # 2. Append to local leads.json
    try:
        leads: List[Dict[str, Any]] = []
        if LEADS_FILE.exists():
            with open(LEADS_FILE, "r", encoding="utf-8") as f:
                leads = json.load(f)
        leads.append(lead_record)
        with open(LEADS_FILE, "w", encoding="utf-8") as f:
            json.dump(leads, f, indent=2)
    except Exception as err:
        print(f"[Warning] Failed to write lead to {LEADS_FILE}: {err}")

    # STUB NOTE: To send real email, insert smtplib or Resend/SendGrid call here.
    return True


def log_handoff(
    reason: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    lead_info: Optional[Dict[str, Any]] = None,
) -> bool:
    """Record a human handoff event for clinical care coordination.
    
    Appends the event to handoffs.json and displays a console notification.
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    handoff_record = {
        "timestamp": timestamp,
        "reason": reason,
        "message_count": len(conversation_history) if conversation_history else 0,
        "lead_info": lead_info or {},
    }

    print("\n" + "-" * 60)
    print("👤 [HUMAN HANDOFF EVENT TRIGGERED]")
    print(f"Timestamp:  {timestamp}")
    print(f"Reason:     {reason}")
    print(f"Turn Count: {handoff_record['message_count']}")
    print("-" * 60 + "\n")

    try:
        handoffs: List[Dict[str, Any]] = []
        if HANDOFFS_FILE.exists():
            with open(HANDOFFS_FILE, "r", encoding="utf-8") as f:
                handoffs = json.load(f)
        handoffs.append(handoff_record)
        with open(HANDOFFS_FILE, "w", encoding="utf-8") as f:
            json.dump(handoffs, f, indent=2)
    except Exception as err:
        print(f"[Warning] Failed to write handoff to {HANDOFFS_FILE}: {err}")

    return True
