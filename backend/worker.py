import os
import sys
import multiprocessing
from rq import Connection, Worker, Queue
from redis import Redis

# Avoid fork-related issues on macOS
if sys.platform == 'darwin':
    os.environ['OBJC_DISABLE_INITIALIZE_FORK_SAFETY'] = 'YES'
    multiprocessing.set_start_method('spawn', force=True)

# Configure your Redis connection
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
conn = Redis.from_url(redis_url)

# Define the queues to listen to
queues = ['default']

def worker_main():
    with Connection(conn):
        worker = Worker(queues)
        worker.work()

if __name__ == '__main__':
    worker_main()