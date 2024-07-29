import multiprocessing
from worker import worker_main

if __name__ == '__main__':
    multiprocessing.set_start_method('spawn', force=True)
    worker_main()