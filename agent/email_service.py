# email_service.py
# Gmail SMTP email delivery service for MindBridge / Ellen practice inquiries.
# Connects to Google Gmail SMTP (smtp.gmail.com:587) with STARTTLS
# to deliver incoming lead capture form notifications directly to your Gmail inbox.

import html
import logging
import os
import smtplib
import ssl
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


def get_smtp_config() -> Dict[str, Any]:
    """Retrieve and validate Gmail SMTP credentials from environment variables."""
    # Support GMAIL_USER / GMAIL_APP_PASSWORD, falling back to SMTP_USER / SMTP_PASSWORD
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
        "gmail_user": gmail_user,
        "gmail_app_password": gmail_app_password,
        "notification_email": notification_email,
        "smtp_server": smtp_server,
        "smtp_port": smtp_port,
        "is_configured": bool(gmail_user and gmail_app_password),
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


def send_practice_inquiry_email(inquiry: Dict[str, Any]) -> Dict[str, Any]:
    """Deliver a practice inquiry notification email via Gmail SMTP.

    Returns a dict with:
      - {"status": "success", "recipient": email} if delivered
      - {"status": "skipped", "message": reason} if credentials not set
      - {"status": "error", "error": error_message} if delivery failed
    """
    config = get_smtp_config()

    if not config["is_configured"]:
        logger.warning(
            "[Gmail SMTP] GMAIL_USER or GMAIL_APP_PASSWORD is not set in environment. "
            "Skipping email delivery. Inquiry is safely saved to Google Sheets and local JSON."
        )
        return {
            "status": "skipped",
            "message": "GMAIL_USER or GMAIL_APP_PASSWORD not configured. Please add them to your environment.",
        }

    sender_email = config["gmail_user"]
    recipient_email = config["notification_email"]
    practice_name = inquiry.get("practice_name", "Unknown Practice")
    contact_name = inquiry.get("name", "Visitor")

    # Construct MIME message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🔔 New Practice Inquiry: {practice_name} ({contact_name})"
    msg["From"] = f"Ellen Assistant <{sender_email}>"
    msg["To"] = recipient_email
    if inquiry.get("email"):
        msg["Reply-To"] = str(inquiry["email"])

    # Attach plain text and HTML alternatives
    part_plain = MIMEText(format_inquiry_plain_text(inquiry), "plain", "utf-8")
    part_html = MIMEText(format_inquiry_html(inquiry), "html", "utf-8")
    msg.attach(part_plain)
    msg.attach(part_html)

    # Dispatch via Gmail SMTP with STARTTLS
    try:
        logger.info(
            f"[Gmail SMTP] Connecting to {config['smtp_server']}:{config['smtp_port']} as {sender_email}..."
        )
        context = ssl.create_default_context()
        with smtplib.SMTP(config["smtp_server"], config["smtp_port"], timeout=15) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(sender_email, config["gmail_app_password"])
            server.sendmail(sender_email, [recipient_email], msg.as_string())

        logger.info(f"[OK] [Gmail SMTP] Notification delivered successfully to {recipient_email}")
        return {
            "status": "success",
            "recipient": recipient_email,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }

    except smtplib.SMTPAuthenticationError as auth_err:
        err_msg = (
            f"Gmail SMTP authentication failed: {auth_err}. "
            "Google requires a 16-character App Password. Generate one at https://myaccount.google.com/apppasswords"
        )
        logger.error(f"[Gmail SMTP] {err_msg}")
        return {"status": "error", "error": err_msg}

    except Exception as exc:
        err_msg = f"Failed to send Gmail notification email: {type(exc).__name__}: {exc}"
        logger.error(f"[Gmail SMTP] {err_msg}", exc_info=True)
        return {"status": "error", "error": err_msg}
