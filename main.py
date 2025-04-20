from logs import global_logger
import threading
import time
import code
from importlib import reload
import atexit
from abc import ABC, abstractmethod
from dotenv import load_dotenv

"""
Main script for AutoAquaponics system.

This script contains a Task class that defines a task that can run concurrently,
as well as a TaskHandle class that can be used to run tasks in separate threads.
The script starts a REPL that can be used to manage these tasks.

To create a task, use the REPL to import the desired module, e.g. `import
notifs`, which contains a definition of the Task class. Then, run task using the
TaskHandle constructor, passing in a valid Task object: `task_notifs =
TaskHandle(notifs.Notifs())`. In addition to storing the resulting task object
in a variable, the task will be added to the `TaskHandle.instances` list. To
stop a task, call the `stop` method on the handle, e.g. `task_notifs.stop()`. To
hot-swap a running module, use `reload(<module>)`, and start the task again. It
is recommended to stop an existing task using a module before reloading the
module.
"""

class Task(ABC):
    @abstractmethod
    def start(self):
        """Start the task. Called INSIDE this task's dedicated thread."""
        pass

    @abstractmethod
    def stop(self):
        """Stop the task. Called OUTSIDE this task's dedicated thread."""
        pass

class TaskHandle:
    instances = []

    def __init__(self, task: Task):
        self.start_time = time.time()
        self.task = task
        self.thread = threading.Thread(target=task.start, daemon=True)
        self.thread.start()
        TaskHandle.instances.append(self)
        global_logger.info(f"started task: {self}")

    def stop(self):
        self.task.stop()
        self.thread.join()
        TaskHandle.instances.remove(self)
        global_logger.info(f"stopped task: {self}")

    def __repr__(self):
        return f"TaskHandle(thread={self.thread.name}, start_time={self.start_time}, task={self.task})"

    @staticmethod
    def stop_all():
        global_logger.info("stopping all tasks...")
        while TaskHandle.instances:
            handle = TaskHandle.instances[0]
            handle.stop()
        global_logger.info("all tasks stopped")

if __name__ == "__main__":
    try:
        global_logger.info("starting main script")
        atexit.register(TaskHandle.stop_all)

        # Load environment variables from .env file
        load_dotenv()

        # start tasks
        import stream
        stream_task = TaskHandle(stream.Stream())
        import server
        server_task = TaskHandle(server.Server())
        import notifs
        notifs_task = TaskHandle(notifs.Notifs())
        import sensors
        sensors_task = TaskHandle(sensors.SensorDataCollector())

        # enter interactive REPL to allow management and hot-reloading
        code.InteractiveConsole(locals=globals()).interact()
    except Exception as e:
        global_logger.error(f"error in main: {str(e)}", exc_info=True)
    finally:
        global_logger.info("shutting down")
