from logs import global_logger
import time
import atexit
import pykka
import dotenv
import sys

from firebase import Firebase
from notifs import Notifs
from stream import Stream
from sensors import Sensors
from server import Server

"""
Main script for AutoAquaponics system.
"""

# load environment variables from .env file
dotenv.load_dotenv()

actor_server = None
actor_firebase = None
actor_notifs = None
actor_stream = None

def main():
    try:
        global_logger.info("Hello World!")

        # initialize the server actor
        global actor_server
        global_logger.debug("starting server actor")
        actor_server = Server.start()

        # initialize the firebase actor
        global actor_firebase
        global_logger.debug("starting firebase actor")
        actor_firebase = Firebase.start()

        # initialize the notifs actor
        global actor_notifs
        global_logger.debug("starting notifs actor")
        actor_notifs = Notifs.start(actor_firebase)

        # initialize the sensors actor
        global actor_sensors
        global_logger.debug("starting sensors actor")
        actor_sensors = Sensors.start(actor_firebase)

        # initialize the stream
        global actor_stream
        global_logger.debug("starting stream actor")
        actor_stream = Stream.start()
        actor_stream.tell("start")

        # keep alive forever
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        global_logger.info("shutting down due to keyboard interrupt")
    except Exception as e:
        global_logger.error(f"error in main: {str(e)}", exc_info=True)

    # clean up actors when program exits
    global_logger.debug("stopping all actors")
    pykka.ActorRegistry.stop_all()
    global_logger.info("Goodbye!")

if __name__ == "__main__":
    main()
