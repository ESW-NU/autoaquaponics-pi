from logs import global_logger
import time
import atexit
import pykka
import dotenv

from firebase import Firebase
from notifs import Notifs
from stream import Stream
from sensors import Sensors

"""
Main script for AutoAquaponics system.
"""

def shut_down():
    global_logger.info("shutting down")

    # clean up actors when program exits
    global_logger.info("stopping all actors")
    pykka.ActorRegistry.stop_all()
atexit.register(shut_down)

# load environment variables from .env file
dotenv.load_dotenv()

actor_dummy = None
actor_firebase = None
actor_notifs = None
actor_stream = None

def main():
    try:
        global_logger.info("starting main script")

        # initialize the firebase actor
        global actor_firebase
        global_logger.info("starting firebase actor")
        actor_firebase = Firebase.start()

        # initialize the notifs actor
        global actor_notifs
        global_logger.info("starting notifs actor")
        actor_notifs = Notifs.start(actor_firebase)

        # initialize the sensors actor
        global actor_sensors
        global_logger.info("starting sensors actor")
        actor_sensors = Sensors.start(actor_firebase)

        # initialize the stream
        global actor_stream
        global_logger.info("starting stream actor")
        actor_stream = Stream.start()
        actor_stream.tell("start")

        # keep alive forever
        while True:
            time.sleep(1)
    except Exception as e:
        global_logger.error(f"error in main: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main()
