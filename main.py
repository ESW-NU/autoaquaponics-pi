from logs import global_logger
import time
import atexit
import pykka

from dummy import Dummy
from firebase import Firebase
from stream import Stream

"""
Main script for AutoAquaponics system.
"""

def shut_down():
    global_logger.info("shutting down")

    # clean up actors when program exits
    global_logger.info("stopping all actors")
    pykka.ActorRegistry.stop_all()
atexit.register(shut_down)

actor_dummy = None
actor_stream = None

def main():
    try:
        global_logger.info("starting main script")

        global actor_dummy
        global_logger.info("starting dummy actor")
        actor_dummy = Dummy().start()
        actor_dummy.tell("start")

        global actor_firebase
        global_logger.info("starting firebase actor")
        actor_firebase = Firebase().start()
        actor_firebase.tell("start")

        # initialize the stream
        global actor_stream
        global_logger.info("starting stream actor")
        actor_stream = Stream().start()
        actor_stream.tell("start")

        # keep alive forever
        while True:
            time.sleep(1)
    except Exception as e:
        global_logger.error(f"error in main: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main()
