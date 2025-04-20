import os
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from .logs import global_logger
from .main import Task
from .firebase import db
from firebase_admin import firestore

# Email configuration
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
SLACK_MESSAGE_ENDPOINT = os.getenv('SLACK_MESSAGE_ENDPOINT')
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

def _send_email(recipient, subject, body):
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
        global_logger.info(f"email sent successfully to {recipient}")
    except Exception as e:
        global_logger.warning(f"failed to send email to {recipient}: {e}")

def _send_slack_msg(text):
    myobj = {"text": text}
    try:
        requests.post(SLACK_MESSAGE_ENDPOINT, json = myobj)
        global_logger.info("Slack message sent successfully")
    except Exception as e:
        global_logger.warning(f"failed to send Slack message: {e}")

def _get_tolerances():
    """Retrieve tolerances from Firebase."""
    tolerances = {}
    tolerances_ref = db.collection('tolerances')
    docs = tolerances_ref.stream()
    for doc in docs:
        tolerances[doc.id] = doc.to_dict()
    if tolerances:
        global_logger.debug(f"retrieved tolerances: {tolerances}")
        return tolerances
    else:
        global_logger.warning("no tolerances found in Firebase")
        return {}

def _check_tolerances(sensor_data, tolerances):
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
            global_logger.warning(f"no tolerance defined for {field}")

    global_logger.debug(f"alerts generated: {alerts}")
    return alerts

def _get_notification_recipients():
    """Retrieve users who have opted in for email notifications."""
    users_ref = db.collection('users')
    query = users_ref.where(filter=firestore.FieldFilter("email_notifications", "==", True))
    recipients = [user.to_dict()['email'] for user in query.stream()]
    global_logger.debug(f"notification recipients: {recipients}")
    return recipients

class Notifs(Task):
    def __init__(self):
        self.watch = None
        self.first_time = True

    def start(self):
        global_logger.info("starting real-time monitoring of sensor data")
        stats_ref = db.collection('stats')
        query = stats_ref.order_by("unix_time", direction=firestore.Query.DESCENDING).limit(1)
        self.watch = query.on_snapshot(self._handle_sensor_update)
        global_logger.info("set up Firebase snapshot listener")

    def stop(self):
        global_logger.info("received stop event; stopping Firebase snapshot listener")
        self.watch.unsubscribe()
        # you may still get a "Background thread did not exit" message if the
        # listener thread hadn't stopped yet. this is okay.

    def _handle_sensor_update(self, doc_snapshot, changes, read_time):
        """Handle real-time updates to sensor data."""
        global_logger.debug("received sensor update")
        for doc in doc_snapshot:
            sensor_data = doc.to_dict()
            global_logger.debug(f"processing sensor data: {sensor_data}")
            tolerances = _get_tolerances()
            if not tolerances:
                global_logger.info("no tolerances defined")
                return

            alerts = _check_tolerances(sensor_data, tolerances)
            if alerts:
                recipients = _get_notification_recipients()
                subject = "Aquaponics System Alert"
                body = "The following issues were detected:\n\n" + "\n".join(alerts)

                global_logger.info(f"alerts generated for this update: {repr(body)}")
                if not self.first_time:
                    for recipient in recipients:
                        _send_email(recipient, subject, body)
                    _send_slack_msg(body)
            else:
                global_logger.info("no alerts generated for this update")
            self.first_time = False

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
    global_logger.info(f"added: {test_data}")

if __name__ == "__main__":
    notifs = None
    try:
        notifs = Notifs().start()
    except KeyboardInterrupt:
        global_logger.info("received keyboard interrupt")
        notifs.stop()
