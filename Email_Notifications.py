import os
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from dotenv import load_dotenv
import requests 

# Load environment variables from .env file
load_dotenv()

# Initialize Firebase
service_account_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH')
cred = credentials.Certificate(service_account_path)
firebase_admin.initialize_app(cred)
db = firestore.client()

# Email configuration
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
SLACK_MESSAGE_ENDPOINT = os.getenv('SLACK_MESSAGE_ENDPOINT')
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

def send_slack_msg(text):
    myobj = {"text": text}
    requests.post(SLACK_MESSAGE_ENDPOINT, json = myobj)

def get_tolerances():
    """Retrieve tolerances from Firebase."""
    tolerances = {}
    tolerances_ref = db.collection('tolerances')
    docs = tolerances_ref.stream()
    for doc in docs:
        tolerances[doc.id] = doc.to_dict()
    if tolerances:
        print(f"Retrieved tolerances: {tolerances}")
        return tolerances
    else:
        print("No tolerances found in Firebase")
        return {}

def check_tolerances(sensor_data, tolerances):
    """Check if sensor data is within tolerances."""
    alerts = []
    fields_to_check = ['TDS', 'air_temp', 'distance', 'humidity', 'pH', 'water_temp']
    
    for field in fields_to_check:
        if field in sensor_data and field in tolerances:
            value = sensor_data[field]
            tolerance_data = tolerances[field]
            min_val = tolerance_data.get('min')
            max_val = tolerance_data.get('max')
            if min_val is not None and max_val is not None:
                if value < min_val or value > max_val:
                    alerts.append(f"{field} is out of range: {value} (safe range: {min_val}-{max_val})")
            elif min_val is not None and value < min_val:
                alerts.append(f"{field} is below minimum: {value} (minimum: {min_val})")
            elif max_val is not None and value > max_val:
                alerts.append(f"{field} is above maximum: {value} (maximum: {max_val})")
        elif field in sensor_data and field not in tolerances:
            print(f"Warning: No tolerance defined for {field}")
    
    print(f"Alerts generated: {alerts}")
    return alerts

def get_notification_recipients():
    """Retrieve users who have opted in for email notifications."""
    users_ref = db.collection('users')
    query = users_ref.where(filter=firestore.FieldFilter("email_notifications", "==", True))
    recipients = [user.to_dict()['email'] for user in query.stream()]
    print(f"Notification recipients: {recipients}")
    return recipients

def handle_sensor_update(doc_snapshot, changes, read_time):
    """Handle real-time updates to sensor data."""
    print("Received sensor update")
    for doc in doc_snapshot:
        sensor_data = doc.to_dict()
        print(f"Processing sensor data: {sensor_data}")
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
            send_slack_msg(body)
        else:
            print("No alerts generated for this update")

def listen_for_sensor_updates():
    """Set up a real-time listener for sensor data updates."""
    stats_ref = db.collection('stats')
    query = stats_ref.order_by("unix_time", direction=firestore.Query.DESCENDING).limit(1)
    query.on_snapshot(handle_sensor_update)
    print("Listener set up successfully")

def add_test_data(db):
    """Add test data to Firestore to simulate out-of-range readings."""
    test_data = {
        "TDS": 1000,  # Assuming this is out of range
        "air_temp": 35,  # Assuming this is out of range
        "distance": 50,
        "humidity": 80,
        "pH": 7,
        "water_temp": 25,
        "unix_time": int(time.time())
    }
    db.collection('stats').add(test_data)
    print(f"Test data added: {test_data}")

def main():
    """Main function to start the real-time listener."""
    print("Starting real-time monitoring of sensor data...")
    listen_for_sensor_updates()
    
    # Add test data after a short delay
    time.sleep(5)
    # add_test_data(db)

    # Keep the main thread alive
    try:
        while True:
            time.sleep(10)
            print("Still listening...")
    except KeyboardInterrupt:
        print("Stopping the monitoring process...")

if __name__ == "__main__":
    main()