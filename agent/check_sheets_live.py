# check_sheets_live.py
# Verify whether real Google Sheets credentials and connection work or if it's mocked.

import json
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

AGENT_DIR = Path(__file__).resolve().parent
load_dotenv(AGENT_DIR / ".env")
load_dotenv(AGENT_DIR.parent / ".env")

import sheets

print("=" * 60)
print("GOOGLE SHEETS DIAGNOSTIC CHECK")
print("=" * 60)

creds_path_env = os.environ.get("GOOGLE_SHEETS_CREDENTIALS_PATH")
sheets_id_env = os.environ.get("GOOGLE_SHEETS_ID")

print(f"GOOGLE_SHEETS_CREDENTIALS_PATH: {creds_path_env}")
print(f"GOOGLE_SHEETS_ID:               {sheets_id_env}")

resolved_path = sheets._find_credentials_path()
print(f"Resolved Credentials File:     {resolved_path}")

try:
    creds = sheets._get_credentials()
    print(f"Credentials Object:            {type(creds)}")
    if creds:
        print(f"Service Account Email:         {getattr(creds, 'service_account_email', 'Unknown')}")
    else:
        print("Credentials Object is None!")
except Exception as e:
    print(f"Error getting credentials: {e}")
    creds = None

if creds and sheets_id_env:
    try:
        import gspread
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(sheets_id_env)
        print(f"\nSpreadsheet Title: '{spreadsheet.title}'")
        worksheets = spreadsheet.worksheets()
        print(f"Worksheets found: {[w.title for w in worksheets]}")

        for w in worksheets:
            all_vals = w.get_all_values()
            print(f"\n--- Tab '{w.title}' ({len(all_vals)} rows) ---")
            for idx, row in enumerate(all_vals[:5]):
                print(f"  Row {idx+1}: {row}")
            if len(all_vals) > 5:
                print(f"  ... and {len(all_vals) - 5} more rows")
                print(f"  Last Row: {all_vals[-1]}")
    except Exception as e:
        print(f"\nError accessing Google Sheet: {e}")
else:
    print("\nCannot attempt connection: missing credentials or sheet ID.")
