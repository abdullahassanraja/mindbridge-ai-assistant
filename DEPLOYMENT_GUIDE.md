# MindBridge Wellness — Deployment Guide

This guide covers deploying the MindBridge FastAPI backend and landing page to **Render**.

---

## 1. Architecture Overview

| Component | Service | Details |
|---|---|---|
| **Vector Database** | Qdrant Cloud | `mindbridge_kb` collection, 38 chunks across 5 documents |
| **LLM Inference** | Groq API | Model: `openai/gpt-oss-120b` |
| **Leads & Scheduling** | Google Sheets | Service Account API with local JSON fallback |
| **Backend API** | Render Web Service | FastAPI with `/health` and `/chat` endpoints |
| **Landing Page** | Render Static Site | Served from `widget/` directory |

---

## 2. Environment Variables

Set these in the Render dashboard for the **API Web Service**. All secret values come from your local `.env` file — never commit them to Git.

| Key | Value | Notes |
|---|---|---|
| `GROQ_API_KEY` | *(from your .env)* | Groq API key (`gsk_...`) |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | LLM model name |
| `QDRANT_URL` | *(from your .env)* | Qdrant Cloud cluster URL |
| `QDRANT_API_KEY` | *(from your .env)* | Qdrant Cloud API key (JWT) |
| `GOOGLE_SHEETS_ID` | *(from your .env)* | Google Sheets workbook ID |
| `GOOGLE_SHEETS_CREDENTIALS_BASE64` | *(see Section 2.1)* | Base64-encoded service account JSON |
| `ALLOWED_ORIGIN` | `https://mindbridge-landing.onrender.com` | Restrict CORS to your static site URL |

### 2.1 Generating `GOOGLE_SHEETS_CREDENTIALS_BASE64`

Base64-encode your service account JSON file and paste the output as the env var value:

```bash
# macOS / Linux:
base64 -w 0 < your-service-account.json

# Windows PowerShell:
[Convert]::ToBase64String([IO.File]::ReadAllBytes("your-service-account.json"))
```

---

## 3. Deploy the API (Render Web Service)

1. Go to [dashboard.render.com](https://dashboard.render.com) → **New +** → **Web Service**.
2. Connect your GitHub repo: `abdullahassanraja/mindbridge-ai-assistant`.
3. Configure:

| Setting | Value |
|---|---|
| **Name** | `mindbridge-ai-assistant` |
| **Region** | Ohio (US East) |
| **Branch** | `main` |
| **Runtime** | Python 3 |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn api.main:app --host 0.0.0.0 --port $PORT` |
| **Instance Type** | Free |

4. Add the **Environment Variables** from Section 2.
5. Click **Create Web Service**.
6. Once deployed, note the live URL (`https://mindbridge-ai-assistant.onrender.com`).
7. Test: visit `https://mindbridge-ai-assistant.onrender.com/health` — should return `{"status": "ok"}`.

---

## 4. Deploy the Landing Page (Render Static Site)

1. Go to [dashboard.render.com](https://dashboard.render.com) → **New +** → **Static Site**.
2. Connect the same GitHub repo: `abdullahassanraja/mindbridge-ai-assistant`.
3. Configure:

| Setting | Value |
|---|---|
| **Name** | `mindbridge-landing` |
| **Branch** | `main` |
| **Publish Directory** | `widget` |
| **Build Command** | *(leave empty)* |

4. Click **Create Static Site**.
5. Once deployed, note the live URL (e.g. `https://mindbridge-landing.onrender.com`).

---

## 5. Post-Deployment: Connect API and Landing Page

After both services are live:

1. **Update `ALLOWED_ORIGIN`** on the API Web Service:
   - Go to your `mindbridge-ai-assistant` service → Environment → edit `ALLOWED_ORIGIN`.
   - Set it to the exact static site URL (or `*` for all origins during testing).
   - Save and let the service redeploy.

2. **Verify `widget.js` backend URL matches your API URL:**
   - The widget auto-detects production vs localhost and defaults to `https://mindbridge-ai-assistant.onrender.com`.
   - Can also be overridden globally via `window.MINDBRIDGE_BACKEND_URL`.

---

## 6. Live Smoke Test

Run these from the deployed landing page to confirm everything works:

| # | Test | Expected Result |
|---|---|---|
| 1 | Open chat widget | Ellen's welcome message appears |
| 2 | Send "hi" → give name → share concern | Qualification flow (name → concern → contact) |
| 3 | "What are your office hours?" | Grounded RAG answer from knowledge base |
| 4 | Describe a couples conflict | Recommends Marcus Reyes, LMFT |
| 5 | Crisis message ("I want to kill myself") | Hardcoded 988/741741/911 crisis response |
| 6 | Follow-up "ok" after crisis | Permanently locked crisis handoff response |
| 7 | "Write me code to sum two numbers" | Scope guard redirect (warm refusal) |
| 8 | Check browser console | No CORS errors |

### Automated Verification

```bash
python test_live_deployment.py https://mindbridge-ai-assistant.onrender.com
```

---

## 7. Free Tier Notes

> **Cold starts:** Render's free tier spins down after 15 minutes of inactivity. The first request after a cold start takes 30–60 seconds. Subsequent requests are fast. Consider warning demo viewers about this delay.

> **FastEmbed model download:** On first deploy, the `BAAI/bge-small-en-v1.5` embedding model (~30 MB) downloads to the Render instance. This happens once per deploy and adds ~60 seconds to the first cold start.
