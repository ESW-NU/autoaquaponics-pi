import os
import firebase_admin
from firebase_admin import credentials, firestore
import pykka
from logs import register_logger

firebase_logger = register_logger("logs/firebase.log", "Firebase")

class Firebase(pykka.ThreadingActor):
    def __init__(self, firebase_logger=firebase_logger):
        super().__init__()
        self.firebase_logger = firebase_logger
        self.db = None
        self.stats_listeners = set()
        self.watch = None

    def on_start(self):
        self.firebase_logger.info("Initializing Firebase")

        service_account_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH')
        if not service_account_path:
            raise ValueError("FIREBASE_SERVICE_ACCOUNT_KEY_PATH environment variable not set")
        cred = credentials.Certificate(service_account_path)
        firebase_admin.initialize_app(cred)

        self.db = firestore.client()
        self._setup_stats_listener()
        self.firebase_logger.info("Firebase initialized successfully")

    def on_receive(self, message):
        self.firebase_logger.debug(f"Received message: {message}")
        if isinstance(message, dict):
            if message.get('type') == 'get_tolerances':
                self.firebase_logger.debug("Getting tolerances")
                return self.get_tolerances()
            elif message.get('type') == 'get_notification_recipients':
                self.firebase_logger.debug("Getting notification recipients")
                return self.get_notification_recipients()
            elif message.get('type') == 'subscribe_to_stats':
                self.firebase_logger.debug("Subscribing to stats")
                self.stats_listeners.add(message['actor_ref'])
                return True
            elif message.get('type') == 'unsubscribe_from_stats':
                self.firebase_logger.debug("Unsubscribing from stats")
                self.stats_listeners.discard(message['actor_ref'])
                return True
            elif message.get('type') == 'add_test_data':
                self.firebase_logger.debug("Adding test data")
                return self.add_test_data()
        self.firebase_logger.warning(f"Received unknown message: {message}")

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
                listener.tell({'type': 'stats_update', 'data': sensor_data})

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

    def add_test_data(self):
        """Add test data to Firestore to simulate out-of-range readings."""
        import time
        test_data = {
            "TDS": 1000,  # Assuming this is out of range
            "air_temp": 35,  # Assuming this is out of range
            "distance": 50,
            "humidity": 80,
            "pH": 7,
            "water_temp": 25,
            "unix_time": int(time.time())
        }
        self.db.collection('stats').add(test_data)
        self.firebase_logger.info(f"Added test data: {test_data}")
        return True
