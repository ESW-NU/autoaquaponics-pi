from logs import global_logger
import time
import atexit
import pykka
import dotenv
import sys

from firebase import Firebase
from notifs import Notifs
from sensors import Sensors
from api_server import Server

"""
Main script for AutoAquaponics system. This script starts all the actors and
keeps them running.

Each actor represents a subsystem. For example, there is an "API server" actor
that handles incoming HTTP requests (and livestream), and a "sensors" actor that
reads from the sensors, and a "firebase" actor that manages interactions with
the cloud. The actors can independently crash without taking down the entire
program.

To access an actor, you can either pass the actor reference directly in a
message if you need that specific actor, or if you just need the subsystem, you
can use the global pykka actor registry:

`lst = pykka.ActorRegistry.get_by_class(SubsystemClassName)`

It is recommended to do the lookup every time you need the actor just in case
it has crashed and respawned since the last lookup.

Remember to check if the list is empty if you want to handle a case where an
actor has crashed.

Once you have a reference to an actor, you can send messages to it in order to
request that it perform certain actions or return certain data. See pykka
documentation (pykka.readthedocs.io) for more information.
"""

# load environment variables from .env file
dotenv.load_dotenv()

def main():
    try:
        global_logger.info("Hello World!")

        # keep alive forever
        while True:
            global_logger.debug("checking and starting actors")

            # Check and start server actor if not running
            if not pykka.ActorRegistry.get_by_class(Server):
                global_logger.debug("starting server actor")
                Server.start()

            # Check and start firebase actor if not running
            if not pykka.ActorRegistry.get_by_class(Firebase):
                global_logger.debug("starting firebase actor")
                Firebase.start()

            # Check and start notifs actor if not running
            if not pykka.ActorRegistry.get_by_class(Notifs):
                global_logger.debug("starting notifs actor")
                Notifs.start()

            # Check and start sensors actor if not running
            if not pykka.ActorRegistry.get_by_class(Sensors):
                global_logger.debug("starting sensors actor")
                Sensors.start()

            global_logger.debug("staying alive")
            time.sleep(60)

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
