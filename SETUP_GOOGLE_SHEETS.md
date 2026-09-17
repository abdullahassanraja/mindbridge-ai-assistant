# Setting Up Google Sheets Integration for MindBridge AI Assistant

This guide explains how to connect your MindBridge AI Assistant to a Google Sheet workbook to automatically record leads and scheduling requests across two separate tabs:
- **Tab 1: "Leads"**
- **Tab 2: "Scheduling Requests"**

---

## Architecture Overview
- **Single Google Sheet Workbook**
- **Tab 1: `Leads`**: Columns: `Timestamp`, `Name`, `Contact Info`, `Stated Concern`, `Matched Therapist (if any)`, `Source (chat/handoff)`, `Session ID`
- **Tab 2: `Scheduling Requests`**: Columns: `Timestamp`, `Name`, `Contact Info`, `Preferred Date`, `Preferred Time`, `Matched Therapist (if any)`, `Session ID`, `Status` (default: "Pending confirmation")
- **Authentication**: Google Cloud Service Account via `gspread` and `google-auth`.
- **Parallel Fail-Safe Fallback**: If the Google Sheets API encounters network or quota errors, the assistant immediately saves records to local JSON files (`leads.json` and `scheduling_requests.json`). The conversation never crashes and no lead is ever lost.

---

## Step-by-Step Setup Guide

### Step 1: Create a Google Cloud Project
1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. Click the project dropdown at the top and select **New Project**.
3. Name your project (e.g., `MindBridge-Assistant`) and click **Create**.

---

### Step 2: Enable Google Sheets and Google Drive APIs
1. In the Google Cloud Console, navigate to **APIs & Services > Library**.
2. Search for **Google Sheets API** and click **Enable**.
3. Search for **Google Drive API** and click **Enable**.
   *(Note: The Drive API is necessary for `gspread` to locate and access files by ID).*

---

### Step 3: Create a Service Account & Download Key
1. In the console, navigate to **APIs & Services > Credentials**.
2. Click **Create Credentials** and choose **Service Account**.
3. Fill in the details:
   - **Service account name**: `mindbridge-sheets-bot`
   - **Service account ID**: (auto-filled, e.g. `mindbridge-sheets-bot@your-project-id.iam.gserviceaccount.com`)
4. Click **Create and Continue**. (Granting project roles is optional; "Viewer" or leaving blank is fine since file-level sharing will be used).
5. Click **Done**.
6. On the Credentials page, click on your newly created Service Account.
7. Go to the **Keys** tab, click **Add Key > Create new key**.
8. Select **JSON** format and click **Create**.
9. A `.json` key file will download to your computer.
10. Move this JSON file into your project workspace (e.g. `c:\Users\pc\Documents\mindbridge\project-youtube-workflow-05d3b547e1be.json`).
    > [!IMPORTANT]
    > Never commit your service account key file to Git. The `.gitignore` file is already pre-configured to ignore `*credentials*.json`, `project-*.json`, and `service_account*.json`.

---

### Step 4: Create the Google Sheets Workbook
1. Open [Google Sheets](https://sheets.google.com) and create a new blank spreadsheet.
2. Rename the spreadsheet to **MindBridge Bot Responses** (or your preferred name).
3. Set up two tabs:
   - Rename the first tab (`Sheet1`) to **`Leads`**.
   - Click the **+** button at the bottom to add a second tab, and rename it to **`Scheduling Requests`**.
4. *(Optional)*: You can leave the sheets empty! The MindBridge integration automatically checks for and inserts the column headers on the first write.
5. Copy the **Spreadsheet ID** from the browser URL:
   ```
   https://docs.google.com/spreadsheets/d/<SPREADSHEET_ID>/edit
   ```
   For example, in:
   `https://docs.google.com/spreadsheets/d/<YOUR_SPREADSHEET_ID>/edit`
   The ID is `<YOUR_SPREADSHEET_ID>`.

---

### Step 5: CRITICAL STEP — Share the Workbook with the Service Account
> [!CAUTION]
> **This is the single most common setup error!**
> A service account has its own unique email address and cannot see any spreadsheet until you explicitly share it.

1. Find the `client_email` in your downloaded service account JSON file, or copy it from the Google Cloud Console (e.g., `mindbridge-sheets-bot@project-youtube-workflow.iam.gserviceaccount.com`).
2. In your Google Sheet, click the green **Share** button in the top right corner.
3. Paste the Service Account's email into the "Add people and groups" box.
4. Set the role dropdown to **Editor**.
5. Uncheck "Notify people" (service accounts have no inbox).
6. Click **Share** (or **Save**).

---

### Step 6: Configure Environment Variables
Add or update the following variables in your `.env` file (and `agent/.env`, `api/.env`):

```env
# Google Sheets Integration
GOOGLE_SHEETS_ID=your_google_sheet_id_here
GOOGLE_SHEETS_CREDENTIALS_PATH=your-service-account.json
```

---

## Verification & Testing
To test that your credentials and workbook are working properly, run:

```bash
python -c "import os, sys; sys.path.insert(0, 'agent'); from dotenv import load_dotenv; load_dotenv('.env'); from sheets import append_lead, append_scheduling_request; print(append_lead({'name': 'Test User', 'contact': 'test@example.com', 'stated_concern': 'Testing Sheets'})); print(append_scheduling_request({'name': 'Test User', 'contact': 'test@example.com', 'preferred_date': 'Tuesday', 'preferred_time': '3pm'}))"
```

You should see:
- `{'local_json': True, 'google_sheets': True}` for both operations.
- The rows will instantly appear in your Google Sheet under the **Leads** and **Scheduling Requests** tabs.
