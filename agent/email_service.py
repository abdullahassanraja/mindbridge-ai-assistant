# email_service.py
# Email delivery service for MindBridge / Ellen practice inquiries.
# Supports:
# 1. Resend HTTP API (Recommended on Render / Cloud: uses HTTPS port 443, never blocked by firewalls)
# 2. Gmail / Direct SMTP (smtp.gmail.com:587 with STARTTLS)

import html
import json
import logging
import os
import re
import smtplib
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

logger = logging.getLogger("mindbridge_email")

# Load environment variables
AGENT_DIR = Path(__file__).resolve().parent
load_dotenv(AGENT_DIR / ".env")
load_dotenv(AGENT_DIR.parent / ".env")
load_dotenv()


def get_email_config() -> Dict[str, Any]:
    """Retrieve and validate email credentials from environment variables."""
    # Reload environment dynamically to pick up any recent .env changes
    load_dotenv(AGENT_DIR / ".env", override=True)
    load_dotenv(AGENT_DIR.parent / ".env", override=True)
    load_dotenv(override=True)

    # 1. Resend HTTP API configuration (Render-friendly HTTPS)
    resend_api_key = os.environ.get("RESEND_API_KEY", "").strip()

    # 2. Gmail / General SMTP configuration
    gmail_user = (
        os.environ.get("GMAIL_USER", "").strip()
        or os.environ.get("SMTP_USER", "").strip()
        or os.environ.get("OUTLOOK_EMAIL", "").strip()
    )
    raw_password = (
        os.environ.get("GMAIL_APP_PASSWORD", "").strip()
        or os.environ.get("SMTP_PASSWORD", "").strip()
        or os.environ.get("OUTLOOK_PASSWORD", "").strip()
    )
    # Strip any spaces automatically (e.g. Google's "abcd efgh ijkl mnop" -> "abcdefghijklmnop")
    gmail_app_password = raw_password.replace(" ", "")
    notification_email = os.environ.get("NOTIFICATION_EMAIL", "").strip() or gmail_user
    smtp_server = os.environ.get("SMTP_SERVER", "").strip() or "smtp.gmail.com"
    smtp_port_raw = os.environ.get("SMTP_PORT", "").strip() or "587"

    try:
        smtp_port = int(smtp_port_raw)
    except ValueError:
        smtp_port = 587

    return {
        "resend_api_key": resend_api_key,
        "gmail_user": gmail_user,
        "gmail_app_password": gmail_app_password,
        "notification_email": notification_email,
        "smtp_server": smtp_server,
        "smtp_port": smtp_port,
        "is_configured": bool(resend_api_key or (gmail_user and gmail_app_password)),
    }


def format_inquiry_html(inquiry: Dict[str, Any]) -> str:
    """Format an incoming inquiry as a clean, branded HTML email."""
    practice_name = html.escape(str(inquiry.get("practice_name", "N/A")))
    name = html.escape(str(inquiry.get("name", "N/A")))
    email_addr = html.escape(str(inquiry.get("email", "N/A")))
    website = str(inquiry.get("website", "") or "").strip()
    website_html = (
        f'<a href="{html.escape(website)}" style="color: #BA3C60; text-decoration: underline;" target="_blank">{html.escape(website)}</a>'
        if website
        else '<span style="color: #888;">Not provided</span>'
    )
    notes = html.escape(str(inquiry.get("notes", "") or "").strip())
    notes_html = (
        f'<div style="background-color: #FFF8FA; border-left: 3px solid #E06D8C; padding: 12px 16px; border-radius: 4px; color: #331323; font-style: italic;">{notes}</div>'
        if notes
        else '<span style="color: #888;">None</span>'
    )
    timestamp_utc = datetime.now(timezone.utc).strftime("%B %d, %Y at %I:%M %p UTC")

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>New Practice Demo Inquiry</title>
</head>
<body style="margin: 0; padding: 24px; background-color: #FFF9FB; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #220B16;">
  <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0">
    <tr>
      <td align="center">
        <table role="presentation" width="600" border="0" cellspacing="0" cellpadding="0" style="background-color: #FFFFFF; border-radius: 18px; border: 1px solid #F8C8D6; box-shadow: 0 4px 20px rgba(201, 75, 110, 0.07); overflow: hidden;">
          <!-- Header Banner -->
          <tr>
            <td style="background: linear-gradient(135deg, #220B16 0%, #381325 100%); padding: 28px 32px; text-align: left;">
              <span style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.5px; color: #F4A6BD; display: block; margin-bottom: 6px;">MindBridge &bull; Ellen Assistant</span>
              <h1 style="margin: 0; font-size: 22px; font-weight: 600; color: #FFFFFF; line-height: 1.3;">New Practice Demo Request</h1>
            </td>
          </tr>
          
          <!-- Content Body -->
          <tr>
            <td style="padding: 32px;">
              <p style="margin: 0 0 20px 0; font-size: 14px; color: #521D38; line-height: 1.6;">
                A practice owner or clinic director just submitted the inquiry form on your website. Here are their details:
              </p>
              
              <!-- Details Table -->
              <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="border-collapse: collapse; margin-bottom: 24px;">
                <tr>
                  <td width="35%" style="padding: 10px 14px; background-color: #FFF5F8; border-bottom: 1px solid #FDE8EE; font-size: 13px; font-weight: 600; color: #94294A;">Practice Name</td>
                  <td style="padding: 10px 14px; background-color: #FFFFFF; border-bottom: 1px solid #FDE8EE; font-size: 14px; font-weight: 700; color: #220B16;">{practice_name}</td>
                </tr>
                <tr>
                  <td style="padding: 10px 14px; background-color: #FFF5F8; border-bottom: 1px solid #FDE8EE; font-size: 13px; font-weight: 600; color: #94294A;">Contact Person</td>
                  <td style="padding: 10px 14px; background-color: #FFFFFF; border-bottom: 1px solid #FDE8EE; font-size: 14px; font-weight: 600; color: #220B16;">{name}</td>
                </tr>
                <tr>
                  <td style="padding: 10px 14px; background-color: #FFF5F8; border-bottom: 1px solid #FDE8EE; font-size: 13px; font-weight: 600; color: #94294A;">Email Address</td>
                  <td style="padding: 10px 14px; background-color: #FFFFFF; border-bottom: 1px solid #FDE8EE; font-size: 14px; color: #220B16;">
                    <a href="mailto:{email_addr}" style="color: #BA3C60; font-weight: 600; text-decoration: none;">{email_addr}</a>
                  </td>
                </tr>
                <tr>
                  <td style="padding: 10px 14px; background-color: #FFF5F8; border-bottom: 1px solid #FDE8EE; font-size: 13px; font-weight: 600; color: #94294A;">Website URL</td>
                  <td style="padding: 10px 14px; background-color: #FFFFFF; border-bottom: 1px solid #FDE8EE; font-size: 14px; color: #220B16;">{website_html}</td>
                </tr>
                <tr>
                  <td style="padding: 10px 14px; background-color: #FFF5F8; border-bottom: 1px solid #FDE8EE; font-size: 13px; font-weight: 600; color: #94294A; vertical-align: top;">Practice Needs</td>
                  <td style="padding: 10px 14px; background-color: #FFFFFF; border-bottom: 1px solid #FDE8EE; font-size: 13.5px; color: #220B16;">{notes_html}</td>
                </tr>
                <tr>
                  <td style="padding: 10px 14px; background-color: #FFF5F8; font-size: 13px; font-weight: 600; color: #94294A;">Submitted At</td>
                  <td style="padding: 10px 14px; background-color: #FFFFFF; font-size: 12.5px; color: #6C5862;">{timestamp_utc}</td>
                </tr>
              </table>

              <!-- Action Button -->
              <div style="text-align: center; margin: 32px 0 16px 0;">
                <a href="mailto:{email_addr}?subject=Re: Your Ellen AI Intake Demo Request for {practice_name}" 
                   style="display: inline-block; background-color: #220B16; color: #FFFFFF; text-decoration: none; padding: 13px 30px; border-radius: 50px; font-size: 13.5px; font-weight: 600; box-shadow: 0 4px 12px rgba(34, 11, 22, 0.2);">
                  Reply Directly to {name} &rarr;
                </a>
              </div>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color: #FFF5F8; padding: 16px 32px; border-top: 1px solid #F8C8D6; text-align: center; font-size: 11.5px; color: #96818C;">
              This notification was generated automatically by the Ellen Assistant website at <a href="https://mindbridge-landing.onrender.com" style="color: #94294A; text-decoration: none;">mindbridge-landing.onrender.com</a>.
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def format_inquiry_plain_text(inquiry: Dict[str, Any]) -> str:
    """Format plain-text fallback for email clients that do not render HTML."""
    practice_name = inquiry.get("practice_name", "N/A")
    name = inquiry.get("name", "N/A")
    email_addr = inquiry.get("email", "N/A")
    website = inquiry.get("website", "") or "Not provided"
    notes = inquiry.get("notes", "") or "None"
    timestamp_utc = datetime.now(timezone.utc).strftime("%B %d, %Y at %I:%M %p UTC")

    return f"""NEW PRACTICE DEMO REQUEST
====================================
Practice Name:  {practice_name}
Contact Person: {name}
Email Address:  {email_addr}
Website URL:    {website}
Practice Needs: {notes}
Submitted At:   {timestamp_utc}
====================================
Reply directly by emailing: {email_addr}
"""


def _send_via_resend(
    api_key: str,
    recipient: str,
    subject: str,
    html_body: str,
    text_body: str,
    reply_to: Optional[str] = None,
) -> Dict[str, Any]:
    """Send notification using Resend HTTP API over HTTPS (port 443, cloud-friendly)."""
    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "MindBridge-Agent/1.0",
    }
    payload: Dict[str, Any] = {
        "from": "Ellen Assistant <onboarding@resend.dev>",
        "to": [recipient],
        "subject": subject,
        "html": html_body,
        "text": text_body,
    }
    if reply_to:
        payload["reply_to"] = reply_to

    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
    )

    try:
        logger.info(f"[Resend API] Sending email notification to {recipient} via HTTPS...")
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))
            msg_id = resp_data.get("id")
            logger.info(f"[OK] [Resend API] Delivered successfully to {recipient} (ID: {msg_id})")
            return {
                "status": "success",
                "service": "resend",
                "recipient": recipient,
                "id": msg_id,
                "sent_at": datetime.now(timezone.utc).isoformat(),
            }
    except urllib.error.HTTPError as http_err:
        err_content = http_err.read().decode("utf-8", errors="replace")
        logger.error(f"[Resend API HTTP Error] {http_err.code}: {err_content}")
        # Detect if Resend rejected due to free tier testing sandbox restriction:
        # e.g., "You can only send testing emails to your own email address (xyz@gmail.com)"
        sandbox_match = re.search(r"to your own email address \(([^)]+)\)", err_content)
        if sandbox_match:
            account_owner_email = sandbox_match.group(1).strip()
            if account_owner_email and account_owner_email.lower() != recipient.lower():
                logger.warning(
                    f"[Resend Sandbox Auto-Fallback] Free tier only allows testing to account owner ({account_owner_email}). "
                    f"Automatically redirecting delivery to verified account: {account_owner_email}..."
                )
                try:
                    payload["to"] = [account_owner_email]
                    retry_req = urllib.request.Request(
                        url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
                    )
                    with urllib.request.urlopen(retry_req, timeout=10) as retry_resp:
                        retry_data = json.loads(retry_resp.read().decode("utf-8"))
                        msg_id = retry_data.get("id")
                        logger.info(
                            f"[OK] [Resend Sandbox Auto-Fallback] Delivered successfully to account owner {account_owner_email} (ID: {msg_id})"
                        )
                        return {
                            "status": "success",
                            "service": "resend",
                            "recipient": account_owner_email,
                            "original_recipient": recipient,
                            "id": msg_id,
                            "sent_at": datetime.now(timezone.utc).isoformat(),
                            "note": f"Delivered to Resend verified account address ({account_owner_email}) due to free tier sandbox restriction.",
                        }
                except Exception as retry_err:
                    logger.error(f"[Resend Auto-Fallback Failed]: {retry_err}")
        return {"status": "error", "error": f"Resend API error {http_err.code}: {err_content}"}
    except Exception as exc:
        logger.error(f"[Resend API Error] {type(exc).__name__}: {exc}")
        return {"status": "error", "error": str(exc)}


def send_practice_inquiry_email(inquiry: Dict[str, Any]) -> Dict[str, Any]:
    """Deliver a practice inquiry notification email.

    Prioritizes Resend HTTP API (if RESEND_API_KEY is configured), then Gmail SMTP.
    Returns:
      - {"status": "success", "recipient": email, ...}
      - {"status": "skipped", "message": reason}
      - {"status": "error", "error": error_message}
    """
    config = get_email_config()

    if not config["is_configured"]:
        logger.warning(
            "[Email Service] Neither RESEND_API_KEY nor GMAIL_USER/GMAIL_APP_PASSWORD is set. "
            "Skipping email delivery. Inquiry is safely saved to Google Sheets and local JSON."
        )
        return {
            "status": "skipped",
            "message": "Email delivery credentials not configured.",
        }

    practice_name = inquiry.get("practice_name", "Unknown Practice")
    contact_name = inquiry.get("name", "Visitor")
    lead_email = str(inquiry.get("email", "")).strip() or None
    recipient_email = config["notification_email"] or config["gmail_user"]
    subject = f"🔔 New Practice Inquiry: {practice_name} ({contact_name})"
    html_body = format_inquiry_html(inquiry)
    text_body = format_inquiry_plain_text(inquiry)

    # 1. If RESEND_API_KEY is configured, try sending via HTTPS
    if config["resend_api_key"]:
        resend_result = _send_via_resend(
            api_key=config["resend_api_key"],
            recipient=recipient_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            reply_to=lead_email,
        )
        if resend_result.get("status") == "success":
            return resend_result
        logger.warning(
            f"[Resend Warning] Resend delivery failed: {resend_result.get('error')}. "
            "Checking if Gmail SMTP fallback is available..."
        )
        if not (config["gmail_user"] and config["gmail_app_password"]):
            return resend_result

    # 2. Fallback to Gmail SMTP (smtp.gmail.com:587)
    sender_email = config["gmail_user"]
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Ellen Assistant <{sender_email}>"
    msg["To"] = recipient_email
    if lead_email:
        msg["Reply-To"] = lead_email

    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        logger.info(
            f"[Gmail SMTP] Connecting to {config['smtp_server']}:{config['smtp_port']} as {sender_email}..."
        )
        context = ssl.create_default_context()
        with smtplib.SMTP(config["smtp_server"], config["smtp_port"], timeout=5) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(sender_email, config["gmail_app_password"])
            server.sendmail(sender_email, [recipient_email], msg.as_string())

        logger.info(f"[OK] [Gmail SMTP] Notification delivered successfully to {recipient_email}")
        return {
            "status": "success",
            "service": "gmail_smtp",
            "recipient": recipient_email,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }

    except smtplib.SMTPAuthenticationError as auth_err:
        err_msg = (
            f"Gmail SMTP authentication failed: {auth_err}. "
            "Google requires a 16-character App Password from https://myaccount.google.com/apppasswords"
        )
        logger.error(f"[Gmail SMTP] {err_msg}")
        return {"status": "error", "error": err_msg}

    except OSError as os_err:
        err_str = str(os_err)
        if "101" in err_str or "unreachable" in err_str.lower():
            err_msg = (
                "Render Free Tier blocks outbound SMTP ports 25, 465, and 587 ([Errno 101] Network is unreachable). "
                "To deliver emails from Render without port blocking, add a free RESEND_API_KEY (from https://resend.com) "
                "to your Render Environment variables, or upgrade Render to a paid instance."
            )
        else:
            err_msg = f"Network socket error during SMTP delivery: {os_err}"
        logger.error(f"[Gmail SMTP Blocked] {err_msg}")
        return {"status": "error", "error": err_msg}

    except Exception as exc:
        err_msg = f"Failed to send notification email: {type(exc).__name__}: {exc}"
        logger.error(f"[Email Error] {err_msg}", exc_info=True)
        return {"status": "error", "error": err_msg}


def format_patient_lead_html(lead: Dict[str, Any]) -> str:
    """Format an incoming patient intake lead as a clean, branded HTML email."""
    name = html.escape(str(lead.get("name", "Anonymous Visitor")))
    contact = html.escape(str(lead.get("contact", "Not provided")))
    need = html.escape(str(lead.get("stated_need", "Intake consultation")))
    therapist = html.escape(str(lead.get("suggested_therapist", "None assigned yet")))
    session_id = html.escape(str(lead.get("session_id", "N/A")))
    source = html.escape(str(lead.get("source", "chat")))
    timestamp_utc = datetime.now(timezone.utc).strftime("%B %d, %Y at %I:%M %p UTC")

    # Reply link
    reply_href = f"mailto:{contact}" if "@" in contact else f"tel:{contact}"

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>New Patient Intake Lead</title>
</head>
<body style="margin: 0; padding: 24px; background-color: #FFF9FB; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #220B16;">
  <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0">
    <tr>
      <td align="center">
        <table role="presentation" width="600" border="0" cellspacing="0" cellpadding="0" style="background-color: #FFFFFF; border-radius: 18px; border: 1px solid #F8C8D6; box-shadow: 0 4px 20px rgba(201, 75, 110, 0.07); overflow: hidden;">
          <tr>
            <td style="background: linear-gradient(135deg, #220B16 0%, #381325 100%); padding: 28px 32px; text-align: left;">
              <span style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.5px; color: #F4A6BD; display: block; margin-bottom: 6px;">MindBridge &bull; Ellen Assistant</span>
              <h1 style="margin: 0; font-size: 22px; font-weight: 600; color: #FFFFFF; line-height: 1.3;">New Client Intake Lead</h1>
            </td>
          </tr>
          <tr>
            <td style="padding: 32px;">
              <p style="margin: 0 0 20px 0; font-size: 14px; color: #521D38; line-height: 1.6;">
                A new client just completed consultation intake with Ellen in the chat assistant. Here are their details:
              </p>
              <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="border-collapse: collapse; margin-bottom: 24px;">
                <tr>
                  <td width="35%" style="padding: 10px 14px; background-color: #FFF5F8; border-bottom: 1px solid #FDE8EE; font-size: 13px; font-weight: 600; color: #94294A;">Client Name</td>
                  <td style="padding: 10px 14px; background-color: #FFFFFF; border-bottom: 1px solid #FDE8EE; font-size: 14px; font-weight: 700; color: #220B16;">{name}</td>
                </tr>
                <tr>
                  <td style="padding: 10px 14px; background-color: #FFF5F8; border-bottom: 1px solid #FDE8EE; font-size: 13px; font-weight: 600; color: #94294A;">Contact Info</td>
                  <td style="padding: 10px 14px; background-color: #FFFFFF; border-bottom: 1px solid #FDE8EE; font-size: 14px; color: #220B16;">
                    <a href="{reply_href}" style="color: #BA3C60; font-weight: 600; text-decoration: none;">{contact}</a>
                  </td>
                </tr>
                <tr>
                  <td style="padding: 10px 14px; background-color: #FFF5F8; border-bottom: 1px solid #FDE8EE; font-size: 13px; font-weight: 600; color: #94294A;">Stated Concern / Need</td>
                  <td style="padding: 10px 14px; background-color: #FFFFFF; border-bottom: 1px solid #FDE8EE; font-size: 13.5px; color: #220B16;">{need}</td>
                </tr>
                <tr>
                  <td style="padding: 10px 14px; background-color: #FFF5F8; border-bottom: 1px solid #FDE8EE; font-size: 13px; font-weight: 600; color: #94294A;">Matched Clinician</td>
                  <td style="padding: 10px 14px; background-color: #FFFFFF; border-bottom: 1px solid #FDE8EE; font-size: 13.5px; color: #220B16;">{therapist}</td>
                </tr>
                <tr>
                  <td style="padding: 10px 14px; background-color: #FFF5F8; border-bottom: 1px solid #FDE8EE; font-size: 13px; font-weight: 600; color: #94294A;">Source / Channel</td>
                  <td style="padding: 10px 14px; background-color: #FFFFFF; border-bottom: 1px solid #FDE8EE; font-size: 13px; color: #6C5862;">{source} (session: {session_id[:12]}...)</td>
                </tr>
                <tr>
                  <td style="padding: 10px 14px; background-color: #FFF5F8; font-size: 13px; font-weight: 600; color: #94294A;">Submitted At</td>
                  <td style="padding: 10px 14px; background-color: #FFFFFF; font-size: 12.5px; color: #6C5862;">{timestamp_utc}</td>
                </tr>
              </table>
              <div style="text-align: center; margin: 32px 0 16px 0;">
                <a href="{reply_href}" 
                   style="display: inline-block; background-color: #220B16; color: #FFFFFF; text-decoration: none; padding: 13px 30px; border-radius: 50px; font-size: 13.5px; font-weight: 600; box-shadow: 0 4px 12px rgba(34, 11, 22, 0.2);">
                  Reach Out to {name} &rarr;
                </a>
              </div>
            </td>
          </tr>
          <tr>
            <td style="background-color: #FFF5F8; padding: 16px 32px; border-top: 1px solid #F8C8D6; text-align: center; font-size: 11.5px; color: #96818C;">
              Logged automatically to Google Sheets ('Leads' tab) by Ellen Assistant.
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def format_patient_lead_plain_text(lead: Dict[str, Any]) -> str:
    """Format plain-text fallback for patient intake leads."""
    name = lead.get("name", "Anonymous Visitor")
    contact = lead.get("contact", "Not provided")
    need = lead.get("stated_need", "Intake consultation")
    therapist = lead.get("suggested_therapist", "None assigned yet")
    session_id = lead.get("session_id", "N/A")
    timestamp_utc = datetime.now(timezone.utc).strftime("%B %d, %Y at %I:%M %p UTC")

    return f"""NEW CLIENT INTAKE LEAD
====================================
Client Name:        {name}
Contact Info:       {contact}
Stated Need:        {need}
Matched Clinician:  {therapist}
Session ID:         {session_id}
Submitted At:       {timestamp_utc}
====================================
Reach out directly: {contact}
"""


def send_patient_lead_email(lead: Dict[str, Any]) -> Dict[str, Any]:
    """Deliver a client intake lead notification email via Resend or SMTP."""
    config = get_email_config()

    if not config["is_configured"]:
        logger.warning("[Email Service] No credentials configured. Skipping client lead email.")
        return {"status": "skipped", "message": "Email delivery credentials not configured."}

    name = lead.get("name", "New Client")
    contact = str(lead.get("contact", "")).strip()
    lead_email = contact if "@" in contact else None
    recipient_email = config["notification_email"] or config["gmail_user"]
    subject = f"🔔 New Client Intake Lead: {name}"
    html_body = format_patient_lead_html(lead)
    text_body = format_patient_lead_plain_text(lead)

    # 1. Resend HTTP API (port 443)
    if config["resend_api_key"]:
        resend_result = _send_via_resend(
            api_key=config["resend_api_key"],
            recipient=recipient_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            reply_to=lead_email,
        )
        if resend_result.get("status") == "success":
            return resend_result
        logger.warning(
            f"[Resend Warning] Resend delivery failed for client lead: {resend_result.get('error')}. "
            "Checking if Gmail SMTP fallback is available..."
        )
        if not (config["gmail_user"] and config["gmail_app_password"]):
            return resend_result

    # 2. Direct SMTP
    sender_email = config["gmail_user"]
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Ellen Assistant <{sender_email}>"
    msg["To"] = recipient_email
    if lead_email:
        msg["Reply-To"] = lead_email

    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(config["smtp_server"], config["smtp_port"], timeout=5) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(sender_email, config["gmail_app_password"])
            server.sendmail(sender_email, [recipient_email], msg.as_string())

        logger.info(f"[OK] [Gmail SMTP] Patient lead email delivered to {recipient_email}")
        return {"status": "success", "service": "gmail_smtp", "recipient": recipient_email}
    except Exception as exc:
        logger.error(f"[Email Error] Failed to send patient lead email: {exc}")
        return {"status": "error", "error": str(exc)}


def format_scheduling_request_html(request_data: Dict[str, Any]) -> str:
    """Format an incoming appointment scheduling request as a clean, branded HTML email."""
    name = html.escape(str(request_data.get("name", "Anonymous Visitor")))
    contact = html.escape(str(request_data.get("contact", "Not provided")))
    pref_date = html.escape(str(request_data.get("preferred_date", "Not specified")))
    pref_time = html.escape(str(request_data.get("preferred_time", "Not specified")))
    therapist = html.escape(str(request_data.get("matched_therapist", "None assigned yet")))
    session_id = html.escape(str(request_data.get("session_id", "N/A")))
    status = html.escape(str(request_data.get("status", "Pending confirmation")))
    timestamp_utc = datetime.now(timezone.utc).strftime("%B %d, %Y at %I:%M %p UTC")

    reply_href = f"mailto:{contact}" if "@" in contact else f"tel:{contact}"

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>New Consultation Scheduling Request</title>
</head>
<body style="margin: 0; padding: 24px; background-color: #FFF9FB; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #220B16;">
  <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0">
    <tr>
      <td align="center">
        <table role="presentation" width="600" border="0" cellspacing="0" cellpadding="0" style="background-color: #FFFFFF; border-radius: 18px; border: 1px solid #F8C8D6; box-shadow: 0 4px 20px rgba(201, 75, 110, 0.07); overflow: hidden;">
          <tr>
            <td style="background: linear-gradient(135deg, #220B16 0%, #381325 100%); padding: 28px 32px; text-align: left;">
              <span style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.5px; color: #F4A6BD; display: block; margin-bottom: 6px;">MindBridge &bull; Ellen Assistant</span>
              <h1 style="margin: 0; font-size: 22px; font-weight: 600; color: #FFFFFF; line-height: 1.3;">📅 New Consultation Scheduling Request</h1>
            </td>
          </tr>
          <tr>
            <td style="padding: 32px;">
              <p style="margin: 0 0 20px 0; font-size: 14px; color: #521D38; line-height: 1.6;">
                A client just submitted a consultation appointment request in chat. Here are their preferred timing & contact details:
              </p>
              <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="border-collapse: collapse; margin-bottom: 24px;">
                <tr>
                  <td width="35%" style="padding: 10px 14px; background-color: #FFF5F8; border-bottom: 1px solid #FDE8EE; font-size: 13px; font-weight: 600; color: #94294A;">Client Name</td>
                  <td style="padding: 10px 14px; background-color: #FFFFFF; border-bottom: 1px solid #FDE8EE; font-size: 14px; font-weight: 700; color: #220B16;">{name}</td>
                </tr>
                <tr>
                  <td style="padding: 10px 14px; background-color: #FFF5F8; border-bottom: 1px solid #FDE8EE; font-size: 13px; font-weight: 600; color: #94294A;">Contact Info</td>
                  <td style="padding: 10px 14px; background-color: #FFFFFF; border-bottom: 1px solid #FDE8EE; font-size: 14px; color: #220B16;">
                    <a href="{reply_href}" style="color: #BA3C60; font-weight: 600; text-decoration: none;">{contact}</a>
                  </td>
                </tr>
                <tr>
                  <td style="padding: 10px 14px; background-color: #FFF5F8; border-bottom: 1px solid #FDE8EE; font-size: 13px; font-weight: 600; color: #94294A;">Preferred Timing</td>
                  <td style="padding: 10px 14px; background-color: #FFFFFF; border-bottom: 1px solid #FDE8EE; font-size: 14px; font-weight: 700; color: #BA3C60;">{pref_date}</td>
                </tr>
                <tr>
                  <td style="padding: 10px 14px; background-color: #FFF5F8; border-bottom: 1px solid #FDE8EE; font-size: 13px; font-weight: 600; color: #94294A;">Matched Clinician</td>
                  <td style="padding: 10px 14px; background-color: #FFFFFF; border-bottom: 1px solid #FDE8EE; font-size: 13.5px; color: #220B16;">{therapist}</td>
                </tr>
                <tr>
                  <td style="padding: 10px 14px; background-color: #FFF5F8; border-bottom: 1px solid #FDE8EE; font-size: 13px; font-weight: 600; color: #94294A;">Booking Status</td>
                  <td style="padding: 10px 14px; background-color: #FFFFFF; border-bottom: 1px solid #FDE8EE; font-size: 13px; font-weight: 600; color: #C94B6E;">{status}</td>
                </tr>
                <tr>
                  <td style="padding: 10px 14px; background-color: #FFF5F8; border-bottom: 1px solid #FDE8EE; font-size: 13px; font-weight: 600; color: #94294A;">Session ID</td>
                  <td style="padding: 10px 14px; background-color: #FFFFFF; border-bottom: 1px solid #FDE8EE; font-size: 12.5px; color: #6C5862;">{session_id[:12]}...</td>
                </tr>
                <tr>
                  <td style="padding: 10px 14px; background-color: #FFF5F8; font-size: 13px; font-weight: 600; color: #94294A;">Requested At</td>
                  <td style="padding: 10px 14px; background-color: #FFFFFF; font-size: 12.5px; color: #6C5862;">{timestamp_utc}</td>
                </tr>
              </table>
              <div style="text-align: center; margin: 32px 0 16px 0;">
                <a href="{reply_href}" 
                   style="display: inline-block; background-color: #220B16; color: #FFFFFF; text-decoration: none; padding: 13px 30px; border-radius: 50px; font-size: 13.5px; font-weight: 600; box-shadow: 0 4px 12px rgba(34, 11, 22, 0.2);">
                  Confirm Availability with {name} &rarr;
                </a>
              </div>
            </td>
          </tr>
          <tr>
            <td style="background-color: #FFF5F8; padding: 16px 32px; border-top: 1px solid #F8C8D6; text-align: center; font-size: 11.5px; color: #96818C;">
              Logged automatically to Google Sheets ('Scheduling Requests' tab) by Ellen Assistant.
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def format_scheduling_request_plain_text(request_data: Dict[str, Any]) -> str:
    """Format plain-text fallback for consultation scheduling requests."""
    name = request_data.get("name", "Anonymous Visitor")
    contact = request_data.get("contact", "Not provided")
    pref_date = request_data.get("preferred_date", "Not specified")
    therapist = request_data.get("matched_therapist", "None assigned yet")
    session_id = request_data.get("session_id", "N/A")
    status = request_data.get("status", "Pending confirmation")
    timestamp_utc = datetime.now(timezone.utc).strftime("%B %d, %Y at %I:%M %p UTC")

    return f"""NEW CONSULTATION SCHEDULING REQUEST
====================================
Client Name:        {name}
Contact Info:       {contact}
Preferred Timing:   {pref_date}
Matched Clinician:  {therapist}
Status:             {status}
Session ID:         {session_id}
Requested At:       {timestamp_utc}
====================================
Confirm availability: {contact}
"""


def send_scheduling_request_email(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """Deliver a consultation scheduling request notification email via Resend or SMTP."""
    config = get_email_config()

    if not config["is_configured"]:
        logger.warning("[Email Service] No credentials configured. Skipping scheduling request email.")
        return {"status": "skipped", "message": "Email delivery credentials not configured."}

    name = request_data.get("name", "New Client")
    contact = str(request_data.get("contact", "")).strip()
    lead_email = contact if "@" in contact else None
    recipient_email = config["notification_email"] or config["gmail_user"]
    pref_date = request_data.get("preferred_date", "")
    subject = f"📅 New Consultation Scheduling Request: {name} ({pref_date})" if pref_date else f"📅 New Consultation Scheduling Request: {name}"
    html_body = format_scheduling_request_html(request_data)
    text_body = format_scheduling_request_plain_text(request_data)

    # 1. Resend HTTP API (port 443)
    if config["resend_api_key"]:
        resend_result = _send_via_resend(
            api_key=config["resend_api_key"],
            recipient=recipient_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            reply_to=lead_email,
        )
        if resend_result.get("status") == "success":
            return resend_result
        logger.warning(
            f"[Resend Warning] Resend delivery failed for scheduling request: {resend_result.get('error')}. "
            "Checking if Gmail SMTP fallback is available..."
        )
        if not (config["gmail_user"] and config["gmail_app_password"]):
            return resend_result

    # 2. Direct SMTP
    sender_email = config["gmail_user"]
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Ellen Assistant <{sender_email}>"
    msg["To"] = recipient_email
    if lead_email:
        msg["Reply-To"] = lead_email

    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(config["smtp_server"], config["smtp_port"], timeout=5) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(sender_email, config["gmail_app_password"])
            server.sendmail(sender_email, [recipient_email], msg.as_string())

        logger.info(f"[OK] [Gmail SMTP] Scheduling request email delivered to {recipient_email}")
        return {"status": "success", "service": "gmail_smtp", "recipient": recipient_email}
    except Exception as exc:
        logger.error(f"[Email Error] Failed to send scheduling request email: {exc}")
        return {"status": "error", "error": str(exc)}

