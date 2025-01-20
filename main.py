from logs import global_logger
import threading
import time
import code
from importlib import reload

"""
Main script for AutoAquaponics system.

This script contains a Task class that can be used to run tasks in separate
threads. The script starts a REPL that can be used to manage these tasks.

To create a task, use the REPL to import the desired module, e.g. `import
notifs`, which must have a valid `main` function. Then, create a task using the
Task constructor: `task_notifs = Task(notifs)`. In addition to storing the
resulting task object in a variable, the task will be added to the
`Task.instances` list. To stop a task, call the `stop` method on the task
object, e.g. `task_notifs.stop()`. To hot-swap a running module, use
`reload(<module>)`, and start the task again. It is recommended to stop an
existing task using a module before reloading the module.
"""

class Task:
    instances = []

    def __init__(self, module):
        self.start_time = time.time()
        self.module = module
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=module.main, args=(self.stop_event,))
        self.thread.start()
        Task.instances.append(self)
        global_logger.info(f"started task: {self}")

    def stop(self):
        self.stop_event.set()
        self.thread.join()
        Task.instances.remove(self)
        global_logger.info(f"stopped task: {self}")

    def __repr__(self):
        return f"Task(module={self.module.__name__}, thread={self.thread.name}, start_time={self.start_time})"

try:
    global_logger.info("starting main script")
    code.InteractiveConsole(locals={"Task": Task, "reload": reload}).interact()
except Exception as e:
    global_logger.error(f"error in main: {str(e)}", exc_info=True)
finally:
    global_logger.info("shutting down")
