# Connecting MindBridge Demo Inquiries to Microsoft Outlook

Whenever a prospective client or clinic director submits the **Practice Inquiry** form on the landing page, Ellen Assistant will automatically send a notification email directly to your Outlook inbox.

---

## 1. Quick Requirements

To allow the MindBridge backend to send emails via Microsoft Outlook SMTP:
1. Your **Outlook / Hotmail / Office 365** email address.
2. A **Microsoft App Password** (16 characters, e.g. `abcd efgh ijkl mnop`).

> [!IMPORTANT]
> Microsoft requires an **App Password** when Two-Factor Authentication (2FA) is turned on for your Microsoft/Outlook account. Your standard account login password will not work for SMTP authentication.

---

## 2. How to Generate Your Microsoft App Password (2 Minutes)

1. Sign in to your Microsoft Account Security page:
   👉 **[account.microsoft.com/security](https://account.microsoft.com/security)**
2. Click on **Advanced Security Options** (or navigate to **Security** → **Manage how I sign in**).
3. Ensure **Two-Step Verification** is turned **ON** (if not already enabled).
4. Scroll down to the **App passwords** section.
5. Click **Create a new app password**.
6. Microsoft will display a 16-character password on screen (e.g. `abcd efgh ijkl mnop`).
7. Copy this password.

---

## 3. Configure Your Environment Variables

### Option A: On Render (Production)
If your backend API is deployed on Render:
1. Open your **Render Dashboard** at [dashboard.render.com](https://dashboard.render.com).
2. Click on your backend service (`mindbridge-ai-assistant`).
3. Click on **Environment** in the left sidebar.
4. Add the following environment variables:
   - `OUTLOOK_EMAIL`: `your_email@outlook.com` (your sending Outlook address)
   - `OUTLOOK_PASSWORD`: `your_16_char_app_password` (without spaces)
   - `NOTIFICATION_EMAIL`: `your_email@outlook.com` (where you want to receive lead alerts)
   - `SMTP_SERVER`: `smtp-mail.outlook.com`
   - `SMTP_PORT`: `587`
5. Click **Save Changes**. Render will automatically redeploy with email delivery active.

---

### Option B: Local Testing (`.env`)
If you test or run the server locally:
1. Open `.env` (or `api/.env`).
2. Fill in the values:
   ```env
   OUTLOOK_EMAIL=your_email@outlook.com
   OUTLOOK_PASSWORD=your_16_char_app_password
   NOTIFICATION_EMAIL=your_email@outlook.com
   SMTP_SERVER=smtp-mail.outlook.com
   SMTP_PORT=587
   ```
3. Restart your local server:
   ```bash
   python api/main.py
   ```

---

## 4. What the Email Notification Looks Like

The email sent to your inbox includes:
- **Practice Name** & **Contact Name**
- **Direct Mailto Reply Button**: One click opens a pre-addressed reply to the lead.
- **Practice Website & Specific Needs**
- **UTC Timestamp**
- **Dual Format**: High-end branded HTML email with clean plain-text fallback.

---

## 5. Graceful Fallback Guarantee

If `OUTLOOK_EMAIL` or `OUTLOOK_PASSWORD` is not set or temporarily unavailable:
- The lead is **always safely recorded** to your Google Sheet (`Practice Inquiries` tab).
- The lead is also saved to local disk backup (`agent/data/leads.json`).
- The website visitor will see the normal confirmation message without any disruption.
