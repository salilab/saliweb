import unittest
import time
import os
import signal
import subprocess
from saliweb.backend import LocalRunner
import testutil
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
        self.assertIsInstance(pid, str)
        # Give the waiter thread enough time to start up
        for i in range(20):
            if pid in LocalRunner._waited_jobs:
                break
            time.sleep(0.05)
        self.assertEqual(LocalRunner._check_completed(pid, ''), False)
        self.assertIn(pid, LocalRunner._waited_jobs)
        os.kill(int(pid), signal.SIGTERM)
        # Give the waiter thread enough time to close down
        for i in range(20):
            if pid not in LocalRunner._waited_jobs:
                break
            time.sleep(0.05)
        self.assertNotIn(pid, LocalRunner._waited_jobs)
        # Make sure that non-zero return code causes a job failure
        event = ws._event_queue.get(timeout=0)
        event.process()
        self.assertIsInstance(ws._exception, OSError)
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
        self.assertIsNone(ws._exception)

    def test_run_directory(self):
        """Make sure that LocalRunner runs in the right directory"""
        ws = DummyWebService()
        with testutil.temp_working_dir() as d:
            r = LocalRunner('echo foo > bar')
            os.chdir(d.origdir)
            # bar should be end up in dir at time of creation, not run
            pid = r._run(ws)
            # wait for completion
            event = ws._event_queue.get()
            os.unlink(os.path.join(d.tmpdir, 'bar'))
            del pid, event

    def test_run_proc(self):
        """Check that LocalRunner jobs from other processes are checked"""
        p = subprocess.Popen('/bin/sleep 60', shell=True)
        pid = str(p.pid)
        self.assertEqual(LocalRunner._check_completed(pid, ''), False)
        os.kill(int(pid), signal.SIGTERM)
        p.wait()
        self.assertEqual(LocalRunner._check_completed(pid, ''), True)


if __name__ == '__main__':
    unittest.main()
