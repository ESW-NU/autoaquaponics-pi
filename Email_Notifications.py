import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import time

# Initialize Firebase
cred = credentials.Certificate("../Desktop/serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# Email configuration
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD")
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
        print(f"Email sent successfully to {recipient}")
    except Exception as e:
        print(f"Failed to send email to {recipient}. Error: {str(e)}")

def get_tolerances():
    """Retrieve tolerances from Firebase."""
    tolerances_doc = db.collection('tolerances').document('system_tolerances').get()
    if tolerances_doc.exists:
        return tolerances_doc.to_dict()
    else:
        print("Tolerances document not found in Firebase")
        return {}

def get_latest_sensor_data():
    """Retrieve the latest sensor data from Firebase."""
    stats_ref = db.collection('stats').order_by('unix_time', direction=firestore.Query.DESCENDING).limit(1)
    docs = stats_ref.stream()
    for doc in docs:
        return doc.to_dict()
    return None

def check_tolerances(sensor_data, tolerances):
    """Check if sensor data is within tolerances."""
    alerts = []
    for key, value in sensor_data.items():
        if key in tolerances and key != 'unix_time':
            min_val, max_val = tolerances[key]
            if value < min_val or value > max_val:
                alerts.append(f"{key} is out of range: {value} (safe range: {min_val}-{max_val})")
    return alerts

def get_notification_recipients():
    """Retrieve users who have opted in for email notifications."""
    users_ref = db.collection('users').where("email_notifications", "==", True)
    return [user.to_dict()['email'] for user in users_ref.stream()]

def check_and_notify():
    """Main function to check sensor data and send notifications if needed."""
    sensor_data = get_latest_sensor_data()
    if not sensor_data:
        print("No sensor data available")
        return

    tolerances = get_tolerances()
    if not tolerances:
        print("No tolerances defined")
        return

    alerts = check_tolerances(sensor_data, tolerances)
    if alerts:
        recipients = get_notification_recipients()
        subject = "Aquaponics System Alert"
        body = "The following issues were detected:\n\n" + "\n".join(alerts)
        
        for recipient in recipients:
            send_email(recipient, subject, body)

def main():
    """Main loop to periodically check and send notifications."""
    check_interval = 15 * 60  # 15 minutes
    while True:
        print("Checking sensor data and sending notifications if needed...")
        check_and_notify()
        time.sleep(check_interval)

if __name__ == "__main__":
    main()