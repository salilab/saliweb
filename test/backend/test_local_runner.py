import unittest
import time
import os
import signal
import subprocess
from saliweb.backend import LocalRunner
import saliweb.backend.events

class DummyJob(object):
    def _try_complete(self, webservice, run_exception):
        if run_exception:
            webservice._exception = run_exception

class DummyWebService(object):
    def __init__(self):
        self._event_queue = saliweb.backend.events._EventQueue()
    def _get_job_by_runner_id(self, runner, runid):
        return DummyJob()

class LocalRunnerTest(unittest.TestCase):
    """Check LocalRunner class"""

    def test_run_wait(self):
        """Check that LocalRunner runs and waits for processes successfully"""
        ws = DummyWebService()
        r = LocalRunner(['/bin/sleep', '60'])
        pid = r._run(ws)
        self.assert_(isinstance(pid, str))
        # Give the waiter thread enough time to start up
        time.sleep(0.1)
        self.assertEqual(LocalRunner._check_completed(pid), False)
        self.assertEqual(pid in LocalRunner._waited_jobs, True)
        os.kill(int(pid), signal.SIGTERM)
        # Give the waiter thread enough time to close down
        time.sleep(0.1)
        self.assertEqual(pid in LocalRunner._waited_jobs, False)
        # Make sure that non-zero return code causes a job failure
        event = ws._event_queue.get(timeout=0)
        event.process()
        self.assert_(isinstance(ws._exception, OSError))
        ws._exception = None

        # Check successful completion
        r1 = LocalRunner(['/bin/echo', 'foo'])
        r2 = LocalRunner(['/bin/echo', 'bar'])
        pid1 = r1._run(ws)
        pid2 = r2._run(ws)
        event1 = ws._event_queue.get()
        event2 = ws._event_queue.get()
        if event1.runid == pid1:
            self.assertEqual(event1.runid, pid1)
            self.assertEqual(event2.runid, pid2)
        else:
            self.assertEqual(event1.runid, pid2)
            self.assertEqual(event2.runid, pid1)
        self.assertEqual(type(event1.runner), LocalRunner)
        self.assertEqual(type(event2.runner), LocalRunner)
        self.assertEqual(ws._exception, None)

    def test_run_proc(self):
        """Check that LocalRunner jobs from other processes are checked"""
        p = subprocess.Popen('/bin/sleep 60', shell=True)
        pid = str(p.pid)
        self.assertEqual(LocalRunner._check_completed(pid), False)
        os.kill(int(pid), signal.SIGTERM)
        p.wait()
        self.assertEqual(LocalRunner._check_completed(pid), True)

if __name__ == '__main__':
    unittest.main()
