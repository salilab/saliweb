import threading
import select
import time
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


class _IncomingJobsEvent(object):
    """Event that represents new incoming job(s)"""
    def __init__(self, webservice):
        self.webservice = webservice

    def process(self):
        self.webservice._process_incoming_jobs()


class _IncomingJobs(threading.Thread):
    """Wait for new incoming jobs"""
    def __init__(self, queue, webservice, sock):
        threading.Thread.__init__(self)
        self.daemon = True
        self.queue = queue
        self.webservice = webservice
        self.sock = sock

    def run(self):
        # Simply emit an IncomingJobsEvent whenever the listening socket is
        # connected to, or every check_minutes regardless
        timeout = self.webservice.config.backend['check_minutes'] * 60
        while True:
            rlist, wlist, xlist = select.select([self.sock], [], [], timeout)
            # Note that currently we don't do anything with the
            # message itself coming in on the socket
            if len(rlist) == 1:
                conn, addr = self.sock.accept()
            self.queue.put(_IncomingJobsEvent(self.webservice))


class _OldJobsEvent(object):
    """Event that represents jobs ready for archival or expiry"""
    def __init__(self, webservice):
        self.webservice = webservice

    def process(self):
        self.webservice._process_old_jobs()


class _OldJobs(threading.Thread):
    """Archive or expire old jobs"""
    def __init__(self, queue, webservice):
        threading.Thread.__init__(self)
        self.daemon = True
        self.queue = queue
        self.webservice = webservice

    def run(self):
        # Simply emit an OldJobsEvent every oldjob_interval
        oldjob_interval = self.webservice._get_oldjob_interval()
        while True:
            time.sleep(oldjob_interval)
            self.queue.put(_OldJobsEvent(self.webservice))
