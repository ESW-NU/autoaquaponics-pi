import pykka
from logs import register_logger
from firebase import StatsUpdate, GetTolerances, GetNotificationRecipients, SubscribeToStats, UnsubscribeFromStats
from email_sender import send_email
from slack_sender import send_slack_message
from dataclasses import dataclass
from typing import List

notifs_logger = register_logger("logs/notifs.log", "Notifications")

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
            notifs_logger.warning(f"no tolerance defined for {field}")

    notifs_logger.debug(f"alerts generated: {alerts}")
    return alerts

@dataclass
class SendAlert:
    """Message to send alerts to notification recipients."""
    alerts: List[str]
    recipients: List[str]

class Notifs(pykka.ThreadingActor):
    def __init__(self, actor_firebase, notifs_logger=notifs_logger):
        super().__init__()
        self.notifs_logger = notifs_logger
        self.actor_firebase = actor_firebase
        self.first_time = True

    def on_start(self):
        self.notifs_logger.info("Starting real-time monitoring of sensor data")
        self.actor_firebase.tell(SubscribeToStats(actor_ref=self.actor_ref))

    def on_stop(self):
        self.notifs_logger.info("Stopping notifications")
        if self.actor_firebase:
            self.actor_firebase.tell(UnsubscribeFromStats(actor_ref=self.actor_ref))
            self.actor_firebase.stop()

    def on_failure(self, failure):
        self.notifs_logger.error(f"Notifications actor failed: {failure}")
        self.on_stop()

    def on_receive(self, message):
        if isinstance(message, StatsUpdate):
            self._handle_sensor_update(message.data)
            return

        self.notifs_logger.warning(f"Received unknown message type: {type(message)}")

    def _handle_sensor_update(self, sensor_data):
        """Handle real-time updates to sensor data."""
        self.notifs_logger.debug(f"Processing sensor data: {sensor_data}")
        tolerances = self.actor_firebase.ask(GetTolerances())
        if not tolerances:
            self.notifs_logger.info("No tolerances defined")
            return

        alerts = _check_tolerances(sensor_data, tolerances)
        if alerts:
            recipients = self.actor_firebase.ask(GetNotificationRecipients())
            subject = "Aquaponics System Alert"
            body = "The following issues were detected:\n\n" + "\n".join(alerts)

            self.notifs_logger.info(f"Alerts generated for this update: {repr(body)}")
            if not self.first_time:
                for recipient in recipients:
                    self.notifs_logger.info(f"Sending email to {recipient}")
                    send_email(recipient, subject, body)
                self.notifs_logger.info(f"Sending slack message")
                send_slack_message(body)
        else:
            self.notifs_logger.info("No alerts generated for this update")
        self.first_time = False

