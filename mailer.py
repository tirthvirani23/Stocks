"""Sends email through an SMTP account (for example a Gmail address with an app password)."""

import smtplib
from email.message import EmailMessage
from email.utils import formataddr

import settings


def send(to: str, subject: str, html: str, text: str = "") -> None:
    user = settings.get("SMTP_USER")
    msg = EmailMessage()
    msg["From"] = formataddr((settings.get("SENDER_NAME", "Indian Stock Checkup"), user))
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text or "Open this email in an app that shows HTML.")
    msg.add_alternative(html, subtype="html")
    host = settings.get("SMTP_HOST", "smtp.gmail.com")
    with smtplib.SMTP_SSL(host, int(settings.get("SMTP_PORT", "465")), timeout=30) as server:
        server.login(user, settings.get("SMTP_PASSWORD").replace(" ", ""))
        server.send_message(msg)
