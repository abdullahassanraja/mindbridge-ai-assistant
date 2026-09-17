# sheets.py
# Google Sheets integration for MindBridge Wellness AI assistant.
# Handles logging leads and scheduling requests to a single workbook with two tabs:
# Tab 1: "Leads"
# Tab 2: "Scheduling Requests"
# With independent parallel fallback to local JSON files (leads.json, scheduling_requests.json).

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

logger = logging.getLogger("mindbridge_sheets")

# Fallback local file paths
AGENT_DIR = Path(__file__).resolve().parent
load_dotenv(AGENT_DIR / ".env")
load_dotenv(AGENT_DIR.parent / ".env")
load_dotenv()

LEADS_JSON_PATH = AGENT_DIR / "leads.json"
SCHEDULING_JSON_PATH = AGENT_DIR / "scheduling_requests.json"

LEADS_TAB_NAME = "Leads"
SCHEDULING_TAB_NAME = "Scheduling Requests"

LEADS_HEADERS = [
    "Timestamp",
    "Name",
    "Contact Info",
    "Stated Concern",
    "Matched Therapist (if any)",
    "Source (chat/handoff)",
    "Session ID",
]

SCHEDULING_HEADERS = [
    "Timestamp",
    "Name",
    "Contact Info",
    "Preferred Date",
    "Preferred Time",
    "Matched Therapist (if any)",
    "Session ID",
    "Status",
]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _find_credentials_path() -> Optional[Path]:
    """Resolve the service account JSON credentials path from environment or project roots."""
    creds_env = os.environ.get("GOOGLE_SHEETS_CREDENTIALS_PATH")
    if creds_env:
        env_path = Path(creds_env)
        if env_path.is_absolute() and env_path.exists():
            return env_path

        # Search candidates relative to cwd, agent_dir, and workspace root
        candidates = [
            Path.cwd() / creds_env,
            AGENT_DIR / creds_env,
            AGENT_DIR.parent / creds_env,
            env_path,
        ]
        for c in candidates:
            if c.exists():
                return c.resolve()

    # Also auto-discover any project-*.json in workspace
    for parent in [Path.cwd(), AGENT_DIR, AGENT_DIR.parent]:
        matched = list(parent.glob("project-*.json"))
        if matched:
            return matched[0].resolve()

    return None


def _get_credentials():
    """Resolve Google service account Credentials from JSON env var, base64 env var, or file."""
    import base64
    from google.oauth2.service_account import Credentials

    # 1. Direct JSON string in GOOGLE_SHEETS_CREDENTIALS_JSON
    raw_json = os.environ.get("GOOGLE_SHEETS_CREDENTIALS_JSON")
    if raw_json and raw_json.strip():
        try:
            info = json.loads(raw_json.strip())
            return Credentials.from_service_account_info(info, scopes=SCOPES)
        except Exception as e:
            logger.warning(f"Could not parse GOOGLE_SHEETS_CREDENTIALS_JSON: {e}")

    # 2. Base64-encoded JSON in GOOGLE_SHEETS_CREDENTIALS_BASE64
    b64_json = os.environ.get("GOOGLE_SHEETS_CREDENTIALS_BASE64")
    if b64_json and b64_json.strip():
        try:
            decoded = base64.b64decode(b64_json.strip()).decode("utf-8")
            info = json.loads(decoded)
            return Credentials.from_service_account_info(info, scopes=SCOPES)
        except Exception as e:
            logger.warning(f"Could not parse GOOGLE_SHEETS_CREDENTIALS_BASE64: {e}")

    # 3. GOOGLE_SHEETS_CREDENTIALS_PATH might contain literal JSON string directly
    creds_env = os.environ.get("GOOGLE_SHEETS_CREDENTIALS_PATH", "").strip()
    if creds_env.startswith("{") and creds_env.endswith("}"):
        try:
            info = json.loads(creds_env)
            return Credentials.from_service_account_info(info, scopes=SCOPES)
        except Exception as e:
            logger.warning(f"Could not parse GOOGLE_SHEETS_CREDENTIALS_PATH as JSON: {e}")

    # 4. Resolve from filesystem path
    creds_file = _find_credentials_path()
    if creds_file and creds_file.exists():
        return Credentials.from_service_account_file(str(creds_file), scopes=SCOPES)

    raise FileNotFoundError(
        f"Google Sheets service account credentials not found. "
        f"Please provide GOOGLE_SHEETS_CREDENTIALS_JSON, GOOGLE_SHEETS_CREDENTIALS_BASE64, "
        f"or a valid file path in GOOGLE_SHEETS_CREDENTIALS_PATH."
    )


def _get_spreadsheet():
    """Authenticate and return the target gspread Spreadsheet instance.
    
    Raises Exception on failure so caller can log and proceed with fallback.
    """
    import gspread

    sheet_id = os.environ.get("GOOGLE_SHEETS_ID", "").strip()
    if not sheet_id:
        raise ValueError("GOOGLE_SHEETS_ID environment variable is not configured.")

    credentials = _get_credentials()
    client = gspread.authorize(credentials)
    spreadsheet = client.open_by_key(sheet_id)
    return spreadsheet


def _get_or_create_worksheet(spreadsheet, tab_name: str, expected_headers: List[str]):
    """Get worksheet by title, or create it if missing, and ensure headers exist."""
    try:
        worksheet = spreadsheet.worksheet(tab_name)
    except Exception:
        # Create worksheet if missing
        worksheet = spreadsheet.add_worksheet(title=tab_name, rows=100, cols=len(expected_headers))

    # Check if empty or missing header
    values = worksheet.get_all_values()
    if not values or not values[0] or all(cell == "" for cell in values[0]):
        worksheet.insert_row(expected_headers, index=1)
    return worksheet


def _append_to_local_json(file_path: Path, record: Dict[str, Any]) -> bool:
    """Save record to a local JSON file array fallback."""
    try:
        records: List[Dict[str, Any]] = []
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    records = json.load(f)
            except Exception:
                records = []
        records.append(record)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)
        return True
    except Exception as err:
        logger.error(f"[Fallback JSON] Failed writing to {file_path}: {err}")
        return False


def append_lead(lead_data: Dict[str, Any]) -> Dict[str, bool]:
    """Append a lead record to Google Sheets 'Leads' tab and local leads.json fallback.
    
    lead_data keys:
    - timestamp: ISO string (optional, defaults to current UTC)
    - name: visitor name
    - contact: email or phone
    - stated_concern: primary issue or need
    - matched_therapist: therapist name or 'None assigned yet'
    - source: 'chat' | 'handoff' (default: 'chat')
    - session_id: session UUID or 'Not provided'
    """
    timestamp = lead_data.get("timestamp") or datetime.now(timezone.utc).isoformat()
    name = lead_data.get("name") or "Anonymous Visitor"
    contact = lead_data.get("contact") or lead_data.get("contact_info") or "Not provided"
    concern = lead_data.get("stated_concern") or lead_data.get("need") or "General inquiry"
    therapist = lead_data.get("matched_therapist") or lead_data.get("suggested_therapist") or "None assigned yet"
    source = lead_data.get("source") or "chat"
    session_id = lead_data.get("session_id") or "Not provided"

    structured_record = {
        "timestamp": timestamp,
        "name": name,
        "contact": contact,
        "stated_concern": concern,
        "matched_therapist": therapist,
        "source": source,
        "session_id": session_id,
        "raw_qualification": lead_data.get("qualification_details", {}),
    }

    results = {"local_json": False, "google_sheets": False}

    # 1. Parallel write to local fallback JSON
    results["local_json"] = _append_to_local_json(LEADS_JSON_PATH, structured_record)

    # 2. Write to Google Sheets
    row = [
        timestamp,
        name,
        contact,
        concern,
        therapist,
        source,
        session_id,
    ]

    for attempt in range(2):
        try:
            spreadsheet = _get_spreadsheet()
            worksheet = _get_or_create_worksheet(spreadsheet, LEADS_TAB_NAME, LEADS_HEADERS)
            worksheet.append_row(row, value_input_option="USER_ENTERED")
            results["google_sheets"] = True
            logger.info(f"[Google Sheets] Successfully appended lead for '{name}' to '{LEADS_TAB_NAME}'.")
            break
        except Exception as err:
            err_str = str(err).lower()
            if attempt == 0 and ("10054" in err_str or "connection" in err_str or "reset" in err_str or "aborted" in err_str):
                import time
                time.sleep(1.0)
                continue
            logger.error(
                f"[Google Sheets Error] Failed appending lead to Sheets: {err}. "
                f"Local fallback record saved: {results['local_json']}"
            )

    return results


def append_scheduling_request(request_data: Dict[str, Any]) -> Dict[str, bool]:
    """Append an appointment request to Google Sheets 'Scheduling Requests' tab and local fallback.
    
    request_data keys:
    - timestamp: ISO string (optional, defaults to current UTC)
    - name: visitor name
    - contact: email or phone
    - preferred_date: requested day/date (free text)
    - preferred_time: requested time of day (free text)
    - matched_therapist: therapist name or 'None assigned yet'
    - session_id: session UUID
    - status: default 'Pending confirmation'
    """
    timestamp = request_data.get("timestamp") or datetime.now(timezone.utc).isoformat()
    name = request_data.get("name") or "Anonymous Visitor"
    contact = request_data.get("contact") or request_data.get("contact_info") or "Not provided"
    pref_date = request_data.get("preferred_date") or "Not specified"
    pref_time = request_data.get("preferred_time") or "Not specified"
    therapist = request_data.get("matched_therapist") or request_data.get("suggested_therapist") or "None assigned yet"
    session_id = request_data.get("session_id") or "Not provided"
    status = request_data.get("status") or "Pending confirmation"

    structured_record = {
        "timestamp": timestamp,
        "name": name,
        "contact": contact,
        "preferred_date": pref_date,
        "preferred_time": pref_time,
        "matched_therapist": therapist,
        "session_id": session_id,
        "status": status,
        "details": request_data.get("details", {}),
    }

    results = {"local_json": False, "google_sheets": False}

    # 1. Parallel write to local fallback JSON
    results["local_json"] = _append_to_local_json(SCHEDULING_JSON_PATH, structured_record)

    # 2. Write to Google Sheets
    row = [
        timestamp,
        name,
        contact,
        pref_date,
        pref_time,
        therapist,
        session_id,
        status,
    ]

    for attempt in range(2):
        try:
            spreadsheet = _get_spreadsheet()
            worksheet = _get_or_create_worksheet(spreadsheet, SCHEDULING_TAB_NAME, SCHEDULING_HEADERS)
            worksheet.append_row(row, value_input_option="USER_ENTERED")
            results["google_sheets"] = True
            logger.info(
                f"[Google Sheets] Successfully appended scheduling request for '{name}' "
                f"to '{SCHEDULING_TAB_NAME}'."
            )
            break
        except Exception as err:
            err_str = str(err).lower()
            if attempt == 0 and ("10054" in err_str or "connection" in err_str or "reset" in err_str or "aborted" in err_str):
                import time
                time.sleep(1.0)
                continue
            logger.error(
                f"[Google Sheets Error] Failed appending scheduling request to Sheets: {err}. "
                f"Local fallback record saved: {results['local_json']}"
            )

    return results
