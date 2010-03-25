import threading
import collections

class _EventQueue(object):
    """A thread-safe FIFO queue"""
    def __init__(self):
        self.lock = threading.RLock()
        self.queue = collections.deque()
        self.cond = threading.Condition(self.lock)

    def put(self, item):
        self.lock.acquire()
        self.queue.append(item)
        self.cond.notify()
        self.lock.release()

    def get(self, timeout=None):
        """Wait for and get the next item from the queue. If timeout is
           given, wait no longer than timeout seconds. If the queue is empty
           after the wait, return None."""
        self.lock.acquire()
        if not self.queue:
            self.cond.wait(timeout)
        try:
            item = self.queue.popleft()
        except IndexError:
            item = None
        self.lock.release()
        return item
