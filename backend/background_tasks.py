import sys
import threading
from logger_setup import logger
from hospital_data_service import hospital_data_service

def run_task_in_background(task_func, *args):
    if sys.platform == 'darwin':
        # On macOS, run the task in a separate thread
        thread = threading.Thread(target=task_func, args=args)
        thread.start()
        return thread
    else:
        # On other platforms, use RQ as before
        from rq import Queue
        from worker import conn
        q = Queue(connection=conn)
        return q.enqueue(task_func, *args)