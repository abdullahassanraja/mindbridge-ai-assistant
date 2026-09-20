# test_email_service.py
# Verification script for Outlook SMTP email service and /api/practice-inquiry endpoint.

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure paths
root_dir = Path(__file__).resolve().parent.parent
agent_dir = root_dir / "agent"
api_dir = root_dir / "api"
sys.path.insert(0, str(agent_dir))
sys.path.insert(0, str(api_dir))

from email_service import send_practice_inquiry_email, format_inquiry_html, format_inquiry_plain_text
from fastapi.testclient import TestClient
from main import app

test_inquiry = {
    "practice_name": "Serenity Counseling & Wellness",
    "name": "Dr. Sarah Mitchell",
    "email": "sarah.mitchell@serenitycounseling.test",
    "website": "https://serenitycounseling.test",
    "notes": "Interested in evaluating Ellen intake bot for 4 licensed therapists.",
}


def test_missing_credentials_graceful_skip():
    """Verify that if credentials are not configured, it skips gracefully without throwing an error."""
    with patch.dict(os.environ, {"OUTLOOK_EMAIL": "", "OUTLOOK_PASSWORD": ""}, clear=False):
        result = send_practice_inquiry_email(test_inquiry)
        assert result.get("status") == "skipped", f"Expected skipped, got: {result}"
        print("[OK] Missing credentials test passed: Gracefully skipped as expected.")


def test_html_and_text_formatting():
    """Verify that HTML and Plain Text formatting contain key inquiry data."""
    html_content = format_inquiry_html(test_inquiry)
    assert "Serenity Counseling &amp; Wellness" in html_content or "Serenity Counseling & Wellness" in html_content
    assert "Dr. Sarah Mitchell" in html_content
    assert "sarah.mitchell@serenitycounseling.test" in html_content
    assert "Interested in evaluating Ellen intake bot" in html_content

    text_content = format_inquiry_plain_text(test_inquiry)
    assert "Serenity Counseling & Wellness" in text_content
    assert "sarah.mitchell@serenitycounseling.test" in text_content
    print("[OK] Email template formatting test passed: Branded HTML and Plain Text formatted correctly.")
 
 
def test_mock_smtp_delivery():
    """Verify that SMTP login and sendmail are properly called with STARTTLS when configured."""
    with patch.dict(os.environ, {
        "OUTLOOK_EMAIL": "demo_sender@outlook.com",
        "OUTLOOK_PASSWORD": "app_password_mock",
        "NOTIFICATION_EMAIL": "demo_inbox@outlook.com",
        "SMTP_SERVER": "smtp-mail.outlook.com",
        "SMTP_PORT": "587"
    }, clear=False):
        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_server = MagicMock()
            mock_smtp_cls.return_value.__enter__.return_value = mock_server

            result = send_practice_inquiry_email(test_inquiry)
            assert result.get("status") == "success", f"Expected success, got: {result}"
            assert result.get("recipient") == "demo_inbox@outlook.com"
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once_with("demo_sender@outlook.com", "app_password_mock")
            mock_server.sendmail.assert_called_once()
            print("[OK] Mock SMTP dispatch test passed: STARTTLS, login, and sendmail verified.")


def test_api_practice_inquiry_endpoint():
    """Verify the FastAPI endpoint /api/practice-inquiry calls both sheets and email service."""
    client = TestClient(app)
    payload = {
        "practice_name": "Lotus Psychology Associates",
        "name": "Dr. Marcus Vance",
        "email": "marcus.vance@lotuspsych.test",
        "website": "https://lotuspsych.test",
        "notes": "Testing integration endpoint."
    }

    with patch.dict(os.environ, {
        "OUTLOOK_EMAIL": "demo_sender@outlook.com",
        "OUTLOOK_PASSWORD": "app_password_mock",
        "NOTIFICATION_EMAIL": "inbox@outlook.com"
    }, clear=False):
        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_server = MagicMock()
            mock_smtp_cls.return_value.__enter__.return_value = mock_server

            response = client.post("/api/practice-inquiry", json=payload)
            assert response.status_code == 200, f"Expected 200, got: {response.status_code} - {response.text}"
            data = response.json()
            assert data["status"] == "ok"
            assert "recorded" in data
            assert data["email"]["status"] == "success"
            print("[OK] API /api/practice-inquiry endpoint test passed: Returned 200 with sheet & email status.")


if __name__ == "__main__":
    print("\n--- RUNNING OUTLOOK EMAIL INTEGRATION TESTS ---")
    test_missing_credentials_graceful_skip()
    test_html_and_text_formatting()
    test_mock_smtp_delivery()
    test_api_practice_inquiry_endpoint()
    print("--- ALL EMAIL INTEGRATION TESTS PASSED SUCCESSFULLY! ---\n")
