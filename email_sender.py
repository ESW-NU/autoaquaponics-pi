import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from logs import register_logger

email_logger = register_logger("logs/email.log", "EmailSender")

# Email configuration
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

def send_email(recipient, subject, body):
    """Send an email using the configured SMTP server."""
    message = MIMEMultipart()
    message["From"] = SENDER_EMAIL
    message["To"] = recipient
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(message)
        email_logger.info(f"Email sent successfully to {recipient}")
        return True
    except Exception as e:
        email_logger.warning(f"Failed to send email to {recipient}: {e}")
        return False