# leads.py
# Lead capture and human handoff notification logging for MindBridge Wellness.

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

LEADS_FILE = Path(__file__).resolve().parent / "leads.json"
HANDOFFS_FILE = Path(__file__).resolve().parent / "handoffs.json"


def _safe_print(msg: str):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('ascii', errors='replace').decode('ascii'))


def send_lead_email(
    name: Optional[str],
    contact: Optional[str],
    need: Optional[str],
    suggested_therapist: Optional[str] = None,
    qualification_info: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
    source: str = "chat",
) -> bool:
    """Format and send a lead notification.
    
    Logs to console, appends to local leads.json fallback, and appends to Google Sheets 'Leads' tab.
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    lead_record = {
        "timestamp": timestamp,
        "name": name or "Anonymous Visitor",
        "contact": contact or "Not provided",
        "stated_need": need or "General inquiry",
        "suggested_therapist": suggested_therapist or "None assigned yet",
        "qualification_details": qualification_info or {},
        "session_id": session_id or "Not provided",
        "source": source,
    }

    # 1. Console notification banner
    _safe_print("\n" + "=" * 60)
    _safe_print("[NEW LEAD NOTIFICATION]")
    _safe_print(f"Time:       {timestamp}")
    _safe_print(f"Name:       {lead_record['name']}")
    _safe_print(f"Contact:    {lead_record['contact']}")
    _safe_print(f"Need:       {lead_record['stated_need']}")
    _safe_print(f"Therapist:  {lead_record['suggested_therapist']}")
    _safe_print(f"Session ID: {lead_record['session_id']}")
    _safe_print(f"Source:     {lead_record['source']}")
    if qualification_info:
        for k, v in qualification_info.items():
            if k not in ("name", "contact"):
                _safe_print(f"  - {k}: {v}")
    _safe_print("=" * 60 + "\n")

    # 2. Append to local leads.json fallback
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

    # 3. Append to Google Sheets 'Leads' tab
    try:
        from sheets import append_lead
        append_lead({
            "timestamp": timestamp,
            "name": lead_record["name"],
            "contact": lead_record["contact"],
            "stated_concern": lead_record["stated_need"],
            "matched_therapist": lead_record["suggested_therapist"],
            "source": source,
            "session_id": lead_record["session_id"],
            "qualification_details": qualification_info or {},
        })
    except Exception as err:
        print(f"[Warning] Google Sheets append_lead error: {err}")

    return True


def log_handoff(
    reason: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    lead_info: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
) -> bool:
    """Record a human handoff event for clinical care coordination.
    
    Appends the event to handoffs.json, displays console notification,
    and logs lead to Sheets if contact or name was provided.
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    handoff_record = {
        "timestamp": timestamp,
        "reason": reason,
        "message_count": len(conversation_history) if conversation_history else 0,
        "lead_info": lead_info or {},
        "session_id": session_id or "Not provided",
    }

    _safe_print("\n" + "-" * 60)
    _safe_print("[HUMAN HANDOFF EVENT TRIGGERED]")
    _safe_print(f"Timestamp:  {timestamp}")
    _safe_print(f"Reason:     {reason}")
    _safe_print(f"Turn Count: {handoff_record['message_count']}")
    _safe_print(f"Session ID: {handoff_record['session_id']}")
    _safe_print("-" * 60 + "\n")

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

    # If lead information was collected prior to handoff, record in Sheets as well
    if lead_info and (lead_info.get("name") or lead_info.get("contact")):
        try:
            from sheets import append_lead
            append_lead({
                "timestamp": timestamp,
                "name": lead_info.get("name", "Anonymous Visitor"),
                "contact": lead_info.get("contact", "Not provided"),
                "stated_concern": lead_info.get("stated_need") or lead_info.get("stated_concern") or f"Handoff: {reason}",
                "matched_therapist": lead_info.get("suggested_therapist", "None assigned yet"),
                "source": "handoff",
                "session_id": session_id or "Not provided",
                "qualification_details": lead_info,
            })
        except Exception as err:
            print(f"[Warning] Google Sheets append_lead in handoff error: {err}")

    return True
