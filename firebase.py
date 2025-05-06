import os
import firebase_admin
from firebase_admin import credentials, firestore
import pykka
from logs import register_logger
from dataclasses import dataclass
from typing import Any
from sensors_data import SensorData

firebase_logger = register_logger("logs/firebase.log", "Firebase")

@dataclass
class GetTolerances:
    """Message to request tolerances from Firebase."""
    pass

@dataclass
class GetNotificationRecipients:
    """Message to request notification recipients from Firebase."""
    pass

@dataclass
class SubscribeToStats:
    """Message to subscribe to stats updates. The specified actor will be sent
    a StatsUpdate message whenever the stats collection is updated."""
    actor_ref: pykka.ActorRef

@dataclass
class UnsubscribeFromStats:
    """Message to unsubscribe from stats updates."""
    actor_ref: pykka.ActorRef

@dataclass
class AddSensorData:
    """Message to add sensor data to Firebase."""
    data: SensorData

@dataclass
class StatsUpdate:
    """Message containing updated stats data."""
    data: dict[str, Any]

class Firebase(pykka.ThreadingActor):
    def __init__(self, firebase_logger=firebase_logger):
        super().__init__()
        self.firebase_logger = firebase_logger
        self.db = None
        self.stats_listeners = set()
        self.watch = None

    def on_start(self):
        try:
            self.firebase_logger.info("Initializing Firebase")

            service_account_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH')
            if not service_account_path:
                raise ValueError("FIREBASE_SERVICE_ACCOUNT_KEY_PATH environment variable not set")
            cred = credentials.Certificate(service_account_path)
            firebase_admin.initialize_app(cred)

            self.db = firestore.client()
            self._setup_stats_listener()
            self.firebase_logger.info("Firebase initialized successfully")
        except Exception as e:
            self.firebase_logger.error(f"Error initializing Firebase: {e}")
            raise e

    def on_receive(self, message):
        self.firebase_logger.debug(f"Received message: {message}")

        if isinstance(message, GetTolerances):
            self.firebase_logger.debug("Getting tolerances")
            return self.get_tolerances()
        elif isinstance(message, GetNotificationRecipients):
            self.firebase_logger.debug("Getting notification recipients")
            return self.get_notification_recipients()
        elif isinstance(message, SubscribeToStats):
            self.firebase_logger.debug("Subscribing to stats")
            self.stats_listeners.add(message.actor_ref)
            return True
        elif isinstance(message, UnsubscribeFromStats):
            self.firebase_logger.debug("Unsubscribing from stats")
            self.stats_listeners.discard(message.actor_ref)
            return True
        elif isinstance(message, AddSensorData):
            self.firebase_logger.debug("Adding sensor data")
            return self.add_sensor_data(message.data)

        self.firebase_logger.warning(f"Received unknown message type: {type(message)}")

    def on_failure(self, failure):
        self.firebase_logger.error(f"Firebase actor failed: {failure}")
        self.shut_down_firebase()

    def on_stop(self):
        self.shut_down_firebase()

    def shut_down_firebase(self):
        self.firebase_logger.info("Shutting down Firebase connection")
        if self.watch:
            self.watch.unsubscribe()
        try:
            firebase_admin.delete_app(firebase_admin.get_app())
            self.firebase_logger.info("Firebase connection shut down successfully")
        except Exception as e:
            self.firebase_logger.error(f"Error shutting down Firebase connection: {e}")

    def _setup_stats_listener(self):
        """Set up a listener for stats collection changes."""
        stats_ref = self.db.collection('stats')
        query = stats_ref.order_by("unix_time", direction=firestore.Query.DESCENDING).limit(1)
        self.watch = query.on_snapshot(self._handle_stats_update)

    def _handle_stats_update(self, doc_snapshot, changes, read_time):
        """Handle real-time updates to sensor data and notify subscribers."""
        for doc in doc_snapshot:
            sensor_data = doc.to_dict()
            self.firebase_logger.debug(f"New sensor data received: {sensor_data}")
            # Notify all subscribers
            for listener in self.stats_listeners:
                listener.tell(StatsUpdate(data=sensor_data))

    def get_tolerances(self):
        """Retrieve tolerances from Firebase."""
        tolerances = {}
        tolerances_ref = self.db.collection('tolerances')
        docs = tolerances_ref.stream()
        for doc in docs:
            tolerances[doc.id] = doc.to_dict()
        if tolerances:
            self.firebase_logger.debug(f"Retrieved tolerances: {tolerances}")
            return tolerances
        else:
            self.firebase_logger.warning("No tolerances found in Firebase")
            return {}

    def get_notification_recipients(self):
        """Retrieve users who have opted in for email notifications."""
        users_ref = self.db.collection('users')
        query = users_ref.where(filter=firestore.FieldFilter("email_notifications", "==", True))
        recipients = [user.to_dict()['email'] for user in query.stream()]
        self.firebase_logger.debug(f"Notification recipients: {recipients}")
        return recipients

    def add_sensor_data(self, data: SensorData):
        """Add sensor data to Firestore."""
        data_dict = data.__dict__
        doc_ref = self.db.collection('stats').add(data_dict)
        doc_id = doc_ref[1].id
        self.firebase_logger.debug(f"Added sensor data with id {doc_id}: {data_dict}")
