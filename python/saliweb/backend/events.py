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


class _PeriodicCheckEvent(object):
    """Event that represents a periodic check for incoming or completed jobs"""
    def __init__(self, webservice):
        self.webservice = webservice

    def process(self):
        self.webservice._process_completed_jobs()
        self.webservice._process_incoming_jobs()


class _IncomingJobsEvent(object):
    """Event that represents new incoming job(s)"""
    def __init__(self, webservice):
        self.webservice = webservice

    def process(self):
        self.webservice._process_incoming_jobs()


class _CleanupIncomingJobsEvent(object):
    """Event that represents cleanup of incoming job directories"""
    def __init__(self, webservice):
        self.webservice = webservice

    def process(self):
        self.webservice._cleanup_incoming_jobs()


class _JobThread(threading.Thread):
    """Base for threads that wait for jobs"""
    def __init__(self, webservice):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self._webservice = webservice


class _PeriodicCheck(_JobThread):
    def run(self):
        # Simply emit a _PeriodicCheckEvent every check_minutes
        timeout = self._webservice.config.backend['check_minutes'] * 60
        while True:
            time.sleep(timeout)
            self._webservice._event_queue.put(_PeriodicCheckEvent(
                                                     self._webservice))


class _IncomingJobs(_JobThread):
    """Wait for new incoming jobs"""
    def __init__(self, webservice, sock):
        _JobThread.__init__(self, webservice)
        self._sock = sock

    def run(self):
        # Simply emit an IncomingJobsEvent whenever the listening socket is
        # connected to
        while True:
            rlist, wlist, xlist = select.select([self._sock], [], [])
            # Note that currently we don't do anything with the
            # message itself coming in on the socket
            if len(rlist) == 1:
                conn, addr = self._sock.accept()
            q = self._webservice._event_queue
            q.put(_IncomingJobsEvent(self._webservice))


class _OldJobsEvent(object):
    """Event that represents jobs ready for archival or expiry"""
    def __init__(self, webservice):
        self.webservice = webservice

    def process(self):
        self.webservice._process_old_jobs()


class _OldJobs(_JobThread):
    """Archive or expire old jobs"""
    def run(self):
        # Simply emit an OldJobsEvent every oldjob_interval
        oldjob_interval = self._webservice._get_oldjob_interval()
        while True:
            time.sleep(oldjob_interval)
            self._webservice._event_queue.put(_OldJobsEvent(self._webservice))


class _CleanupIncomingJobs(_JobThread):
    """Cleanup of abandoned incoming job directories"""
    def run(self):
        # Simply periodically emit a CleanupIncomingJobsEvent
        interval = self._webservice._get_cleanup_incoming_job_times()[0]
        while True:
            time.sleep(interval)
            self._webservice._event_queue.put(
                              _CleanupIncomingJobsEvent(self._webservice))


class _CompletedJobEvent(object):
    """Event to represent a job started by a Runner finishing"""
    def __init__(self, webservice, runner, runid, run_exception):
        self.webservice = webservice
        self.runner = runner
        self.runid = runid
        self.run_exception = run_exception

    def process(self):
        job = self.webservice._get_job_by_runner_id(self.runner, self.runid)
        if job:
            job._try_complete(self.webservice, self.run_exception)
