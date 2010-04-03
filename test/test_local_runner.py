import unittest
import time
import os
import signal
import subprocess
from saliweb.backend import LocalRunner
import saliweb.backend.events

class DummyWebService(object):
    def __init__(self):
        self._event_queue = saliweb.backend.events._EventQueue()

class LocalRunnerTest(unittest.TestCase):
    """Check LocalRunner class"""

    def test_run_wait(self):
        """Check that LocalRunner runs and waits for processes successfully"""
        ws = DummyWebService()
        r = LocalRunner(['/bin/sleep', '60'])
        pid = r._run(ws)
        self.assert_(isinstance(pid, str))
        self.assertEqual(LocalRunner._check_completed(pid), None)
        self.assertEqual(pid in LocalRunner._waited_jobs, True)
        os.kill(int(pid), signal.SIGTERM)
        time.sleep(0.1)
        self.assertEqual(pid in LocalRunner._waited_jobs, False)
        # Make sure that non-zero return code causes a job failure
        event = ws._event_queue.get(timeout=0)
        self.assertRaises(OSError, event.process)

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
