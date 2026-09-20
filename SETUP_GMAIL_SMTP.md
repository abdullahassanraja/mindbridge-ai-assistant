# Connecting MindBridge Demo Inquiries to Gmail SMTP

Whenever a prospective client or clinic director submits the **Practice Inquiry** form on the landing page, Ellen Assistant will automatically send a notification email directly to your Gmail inbox.

---

## 1. Quick Requirements

To send email notifications via Gmail SMTP:
1. Your **Gmail address** (e.g. `yourname@gmail.com`).
2. A **Google App Password** (16 lowercase letters, e.g. `xxxx yyyy zzzz wwww`).

> [!IMPORTANT]
> Google requires an **App Password** for SMTP. Your standard Google account login password will not work because 2-Step Verification protects your account.

---

## 2. How to Generate Your Google App Password (1 Minute)

1. Open the Google Account App Passwords page directly:  
   👉 **[myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)**  
   *(If prompted, sign in to your Google Account).*

2. If you do not have 2-Step Verification enabled:  
   - Enable it first at [myaccount.google.com/signinoptions/two-step-verification](https://myaccount.google.com/signinoptions/two-step-verification).
   - Then return to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).

3. Under **App name**, enter a name like:  
   `MindBridge Assistant` or `Ellen Demo Form`

4. Click **Create**.

5. Google will pop up a modal with a **16-character password** (e.g. `abcd efgh ijkl mnop`).
6. Copy this 16-character code (you can use it with or without spaces; our code strips whitespace automatically).

---

## 3. Configure Your Environment Variables

### Option A: On Render (Production)
1. Open your **Render Dashboard**: [dashboard.render.com](https://dashboard.render.com).
2. Click on your backend service: `mindbridge-ai-assistant`.
3. In the left sidebar, click **Environment**.
4. Add or update these variables:
   - `GMAIL_USER`: `your_email@gmail.com`
   - `GMAIL_APP_PASSWORD`: `your_16_character_app_password`
   - `NOTIFICATION_EMAIL`: `your_email@gmail.com` *(where you want lead notifications sent)*
   - `SMTP_SERVER`: `smtp.gmail.com`
   - `SMTP_PORT`: `587`
5. Click **Save Changes**. Render will automatically redeploy with Gmail notifications active.

---

### Option B: Local Testing (`.env`)
1. Open your `.env` (or `api/.env`) file.
2. Fill in the values:
   ```env
   GMAIL_USER=your_email@gmail.com
   GMAIL_APP_PASSWORD=your_16_character_app_password
   NOTIFICATION_EMAIL=your_email@gmail.com
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   ```
3. Restart your local server:
   ```bash
   python api/main.py
   ```

---

## 4. What the Notification Email Contains

Every inquiry delivered to your Gmail inbox includes:
- **Practice Name** & **Doctor / Director Name**
- **One-Click Reply Button**: Opens your email client pre-addressed to the client.
- **Practice Website & Specific Needs**
- **Exact Submission Timestamp (UTC)**
- **Dual Format**: Branded HTML card with clean plain-text fallback.

---

## 5. Graceful Fallback Guarantee

If `GMAIL_USER` or `GMAIL_APP_PASSWORD` is ever missing or credentials change:
- The lead inquiry is **always saved** to your Google Sheets spreadsheet (`Practice Inquiries` tab).
- The lead is also saved to local disk backup (`agent/data/leads.json`).
- The user on the website sees the normal instant success message without interruption.
