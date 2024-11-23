from logs import global_logger
import threading

def notifs():
	import notifs
	stop = threading.Event()
	thread = threading.Thread(target=notifs.main, args=(stop,))
	thread.start()
	return stop, thread

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
		global_logger.error(f"error running tasks: {str(e)}")

def repl():
	try:
		import code
		code.InteractiveConsole(locals=globals()).interact()
	except Exception as e:
		global_logger.error(f"error in REPL: {str(e)}")
	finally:
		global_logger.info("exited REPL")

try:
	global_logger.info("starting main script")

	run_tasks()

	repl()
except Exception as e:
	global_logger.error(f"error in main script: {str(e)}")
finally:
	global_logger.info("shutting down")
