from logs import global_logger
import threading

"""
Main script for AutoAquaponics system.

This script initializes and runs various tasks required for the AutoAquaponics
system. It includes functionality to start and stop tasks, as well as an
interactive REPL for debugging.

# Important Functions

    stop_task(task_name: str) -> None:
        Stops a running task by its name. Logs the stopping of the task.

    run_tasks() -> None:
        Initializes and starts all required tasks. Logs the start of tasks or
        any errors encountered.

    repl() -> None:
        Starts an interactive REPL for debugging. Logs any errors encountered
        and the exit of the REPL.

# Execution Flow

    The script starts by logging the start of the main script. It then runs the
    required tasks and starts the REPL. Any exceptions during the execution are
    logged. Finally, it logs the shutdown of the script.
"""

def notifs():
    try:
        import notifs
        stop = threading.Event()
        thread = threading.Thread(target=notifs.main, args=(stop,))
        thread.start()
        return stop, thread
    except Exception as e:
        global_logger.error(f"error starting notifications task: {str(e)}", exc_info=True)

tasks = {}

def stop_task(task_name):
	stop_event, thread = tasks[task_name]
	stop_event.set()
	thread.join()
	global_logger.info(f"stopped task '{task_name}'")

def run_tasks():
	try:
		notifs_stop, notifs_thread = notifs()
		tasks["notifs"] = notifs_stop, notifs_thread

		global_logger.info("started tasks")
	except Exception as e:
		global_logger.error(f"error running tasks: {str(e)}", exc_info=True)

def repl():
	try:
		import code
		code.InteractiveConsole(locals=globals()).interact()
	except Exception as e:
		global_logger.error(f"error in REPL: {str(e)}", exc_info=True)
	finally:
		global_logger.info("exited REPL")

try:
	global_logger.info("starting main script")

	run_tasks()

	repl()
except Exception as e:
	global_logger.error(f"error in main script: {str(e)}", exc_info=True)
finally:
	global_logger.info("shutting down")
