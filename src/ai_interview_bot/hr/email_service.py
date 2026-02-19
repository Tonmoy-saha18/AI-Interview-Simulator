"""Email service for sending interview invitations."""

from __future__ import annotations

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


class EmailService:
    """Service for sending emails via SMTP."""

    def __init__(
        self,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        smtp_username: Optional[str] = None,
        smtp_password: Optional[str] = None,
        from_email: Optional[str] = None,
    ) -> None:
        self.smtp_host = smtp_host or os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = smtp_port or int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = smtp_username or os.getenv("SMTP_USERNAME")
        self.smtp_password = smtp_password or os.getenv("SMTP_PASSWORD")
        self.from_email = from_email or os.getenv("SMTP_FROM_EMAIL", self.smtp_username)

    def _create_interview_email(
        self,
        candidate_email: str,
        candidate_name: Optional[str],
        interview_link: str,
        role: str,
        expires_at: datetime,
    ) -> MIMEMultipart:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Interview Invitation - {role}"
        msg["From"] = self.from_email
        msg["To"] = candidate_email

        expires_str = expires_at.strftime("%B %d, %Y at %I:%M %p UTC")
        greeting = f"Dear {candidate_name}," if candidate_name else "Dear Candidate,"

        text_content = f"""\
{greeting}

You have been invited to participate in an AI-powered interview for the position of {role}.

Please click on the link below to start your interview:
{interview_link}

This link will expire on {expires_str}.

Please ensure you have a stable internet connection and are in a quiet environment before starting the interview.

Good luck!

Best regards,
AI Interview Team"""

        html_content = f"""\
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
        .content {{ background-color: #f9f9f9; padding: 30px; border-radius: 0 0 5px 5px; }}
        .button {{ display: inline-block; padding: 12px 30px; background-color: #4CAF50; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
        .button:hover {{ background-color: #45a049; }}
        .footer {{ margin-top: 20px; font-size: 12px; color: #666; }}
        .warning {{ background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 10px; margin: 15px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header"><h2>Interview Invitation</h2></div>
        <div class="content">
            <p>{greeting}</p>
            <p>You have been invited to participate in an AI-powered interview for the position of <strong>{role}</strong>.</p>
            <div style="text-align: center;"><a href="{interview_link}" class="button">Start Interview</a></div>
            <p style="text-align: center;"><a href="{interview_link}" style="color: #4CAF50; word-break: break-all;">{interview_link}</a></p>
            <div class="warning"><strong>Important:</strong> This link will expire on <strong>{expires_str}</strong>.</div>
            <p><strong>Before you begin:</strong></p>
            <ul>
                <li>Ensure you have a stable internet connection</li>
                <li>Find a quiet environment</li>
                <li>Set aside adequate time to complete the interview</li>
            </ul>
            <p>Good luck with your interview!</p>
            <div class="footer">
                <p>Best regards,<br>AI Interview Team</p>
                <p>This is an automated message. Please do not reply to this email.</p>
            </div>
        </div>
    </div>
</body>
</html>"""

        msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))
        return msg

    def send_interview_invitation(
        self,
        candidate_email: str,
        candidate_name: Optional[str],
        interview_link: str,
        role: str,
        expires_at: datetime,
    ) -> bool:
        if not self.smtp_username or not self.smtp_password:
            raise ValueError(
                "SMTP credentials not configured. "
                "Please set SMTP_USERNAME and SMTP_PASSWORD environment variables."
            )

        try:
            msg = self._create_interview_email(
                candidate_email, candidate_name, interview_link, role, expires_at
            )
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            return True
        except Exception as e:
            print(f"Error sending email: {e!s}")
            raise
