# MindBridge Wellness — FastAPI Backend Deployment Guide

This guide details how to deploy the MindBridge FastAPI backend to **Render** (recommended) or **Railway**, and how to verify the live service.

---

## 1. Cloud Architecture Overview

- **Vector Database**: Hosted on **Qdrant Cloud** (`mindbridge_kb` collection, 38 chunks/points across 5 documents).
- **LLM Inference**: **Groq API** (`openai/gpt-oss-120b`).
- **Scheduling & Leads Backend**: **Google Sheets** via Service Account API with local JSON fallback.
- **FastAPI Service**: Serves `/health` and `/chat` with in-memory session persistence.

---

## 2. Environment Variables InventorySet these environment variables in your Render dashboard (values stored in your local `.env` file — never commit real secrets):

| Variable | Value | Notes |
|---|---|---|
| `PORT` | `10000` (Render default) or leave auto | Port assigned by hosting provider |
| `ALLOWED_ORIGIN` | `https://your-static-site.onrender.com` | Restrict to your landing page / Squarespace domain |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | High-speed, high-intelligence model |
| `GROQ_API_KEY` | *(from your local .env)* | Groq API Key |
| `QDRANT_URL` | *(from your local .env)* | Qdrant Cloud Cluster URL |
| `QDRANT_API_KEY` | *(from your local .env)* | Qdrant Cloud API Key |
| `GOOGLE_SHEETS_ID` | *(from your local .env)* | Target Workbook ID |
| `GOOGLE_SHEETS_CREDENTIALS_BASE64` | *(See instructions below)* | Full service account JSON encoded in base64 |

### Value for `GOOGLE_SHEETS_CREDENTIALS_BASE64`
Base64-encode your Google service account JSON file and paste the result into this env var:
```bash
# On macOS/Linux:
base64 -w 0 < your-service-account.json

# On Windows PowerShell:
[Convert]::ToBase64String([IO.File]::ReadAllBytes("your-service-account.json"))
`````

---

## 3. Deploying to Render (Step-by-Step)

1. **Commit and push changes to GitHub**:
   ```bash
   git add .
   git commit -m "feat: Qdrant cloud migration and cloud deployment configs"
   git push origin main
   ```

2. **Create the Web Service on Render**:
   - Go to [dashboard.render.com](https://dashboard.render.com) and log in.
   - Click **New +** → **Web Service**.
   - Connect your GitHub repository (`mindbridge`).
   - Settings:
     - **Name**: `mindbridge-api`
     - **Runtime**: `Python`
     - **Build Command**: `pip install -r requirements.txt`
     - **Start Command**: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
     - **Instance Type**: `Free`

3. **Add Environment Variables**:
   - In the **Environment Variables** section of the service, add the 8 variables listed in the table above.
   - Click **Create Web Service**.

4. **Get your Live URL**:
   - Render will build and deploy the app. Once live, you will see a public URL like:
     `https://mindbridge-api.onrender.com`

---

## 4. Alternate Deployment: Railway

1. Install Railway CLI or go to [railway.app](https://railway.app).
2. Connect your GitHub repository. Railway will detect `railway.json` and `Procfile`.
3. Under **Variables**, add the same environment variables listed in Section 2.
4. Railway will deploy and generate a public domain (e.g. `https://mindbridge-api-production.up.railway.app`).

---

## 5. Live Automated Verification

Once your service is live, run the automated verification script from your terminal:

```bash
python test_live_deployment.py https://mindbridge-api.onrender.com
```

This will automatically:
1. Verify `GET /health` returns `{"status": "ok"}`.
2. Execute a multi-turn conversation (`"hi"` → `"I'm Sarah"` → `"What are your office hours?"`) and assert session persistence and Qdrant Cloud retrieval.
3. Test the crisis safety guardrail on the live deployment to ensure strict 988/911 responses and persistent lock.
