# Connecting MindBridge Demo Inquiries to Email (Gmail / Resend)

Whenever a prospective client or clinic director submits the **Practice Inquiry** form on the landing page, Ellen Assistant will automatically notify your inbox.

---

## ⚡ Why Did the Form Take Long Before?
1. **Instant Response Fix**: We updated the server to use **FastAPI Background Tasks**. When someone submits the form, the server now responds in **< 50 milliseconds** (instant confirmation for the user).
2. **Render Cloud SMTP Blocking**: Render's free tier has an outbound firewall that **blocks traditional SMTP ports (25, 465, and 587)** to prevent spam. When a server on Render free tier tries to connect to `smtp.gmail.com:587`, Render blocks the connection with `[Errno 101] Network is unreachable`.

To deliver emails from Render without any firewall blocking, you have two great options below:

---

## Option 1 (Recommended for Render): Free Resend API (30 Seconds)
**Resend** uses modern HTTPS (port 443), which is **never blocked** by Render or any cloud provider. It sends emails directly into your Gmail inbox.

1. Go to **[resend.com](https://resend.com)** and click **Sign In** (sign in with Google / GitHub).
2. In the left sidebar, click **API Keys** → **Create API Key**.
3. Copy the key (starts with `re_...`).
4. In your **Render Dashboard** (`mindbridge-ai-assistant` → **Environment**), add:
   - `RESEND_API_KEY`: `re_your_api_key_here`
   - `NOTIFICATION_EMAIL`: `your_email@gmail.com` *(your Gmail address)*
5. Click **Save Changes**. Emails will now arrive in your Gmail inbox instantly.

---

## Option 2: Direct Gmail SMTP (For Local Development or Paid Hosting)
If you run locally or on a host that does not block port 587:

1. Open Google Account App Passwords directly:  
   👉 **[myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)**
2. Under **App name**, enter `MindBridge` and click **Create**.
3. Copy the 16-character code (e.g. `abcd efgh ijkl mnop`).
4. In your `.env` (or Render if using a paid tier that allows SMTP):
   ```env
   GMAIL_USER=your_email@gmail.com
   GMAIL_APP_PASSWORD=your_16_character_app_password
   NOTIFICATION_EMAIL=your_email@gmail.com
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   ```

---

## What the Email Notification Looks Like
Every inquiry delivered to your Gmail inbox includes:
- **Practice Name** & **Doctor / Director Name**
- **One-Click Reply Button**: Directly opens a pre-addressed email reply.
- **Practice Website & Specific Needs**
- **Exact Submission Timestamp (UTC)**
- **Dual Format**: Branded HTML card with clean plain-text fallback.

---

## Graceful Fallback Guarantee
- Every lead is **always saved** to your Google Sheet (`Practice Inquiries` tab).
- Every lead is **always saved** to local disk backup (`agent/data/leads.json`).
- Form submission always confirms **instantly** for website visitors.
