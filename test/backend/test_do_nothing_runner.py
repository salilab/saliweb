import unittest
import os
from saliweb.backend import DoNothingRunner
import saliweb.backend.events

class DummyJob(object):
    def _try_complete(self, webservice, run_exception):
        webservice._exception = run_exception

class DummyWebService(object):
    def __init__(self):
        self._event_queue = saliweb.backend.events._EventQueue()
    def _get_job_by_runner_id(self, runner, runid):
        return DummyJob()

class DoNothingRunnerTest(unittest.TestCase):
    """Check DoNothingRunner class"""

    def test_run(self):
        """Check that DoNothingRunner runs"""
        ws = DummyWebService()
        r = DoNothingRunner()
        r._run(ws)
        self.assertEqual(DoNothingRunner._check_completed('none', ''), True)
        event = ws._event_queue.get()
        event.process()
        self.assertEqual(ws._exception, None)
        os.unlink('job-state')

if __name__ == '__main__':
    unittest.main()
