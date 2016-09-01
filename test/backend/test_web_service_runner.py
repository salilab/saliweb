import unittest
import time
import os
from saliweb.backend import SaliWebServiceRunner
import saliweb
import saliweb.backend.events
import testutil

class DummyJob(object):
    def _try_complete(self, webservice, run_exception):
        if run_exception:
            webservice._exception = run_exception

class DummyWebService(object):
    def __init__(self):
        self._event_queue = saliweb.backend.events._EventQueue()
    def _get_job_by_runner_id(self, runner, runid):
        return DummyJob()

class DummyModule(object):
    def __init__(self):
        self.get_results_counter = 0
    def submit_job(self, url, args):
        self.url = url
        self.args = args
        return 'jobid'
    def get_results(self, url):
        self.get_results_counter += 1
        if self.get_results_counter > 2:
            return ['http://foo/result1', 'http://foo/result2']


class Test(unittest.TestCase):
    """Check SaliWebServiceRunner class"""

    def test_run(self):
        """Check that SaliWebServiceRunner runs jobs"""
        oldin = saliweb.backend._SaliWebJobWaiter._start_interval
        old = saliweb.web_service
        dm = DummyModule()
        try:
            saliweb.backend._SaliWebJobWaiter._start_interval = 0.01
            saliweb.web_service = dm
            ws = DummyWebService()
            with testutil.temp_working_dir() as d:
                r = SaliWebServiceRunner('testurl', ['arg1', 'arg2'])
                os.chdir(d.origdir)
                url = r._run(ws)
                self.assertEqual(url, 'jobid')
                event1 = ws._event_queue.get()
                self.assertEqual(event1.run_exception, None)
                self.assertEqual(event1.runid, 'jobid')
                self.assertEqual(event1.runner, r)
                self.assertEqual(event1.webservice, ws)
                # Give the waiter thread enough time to close down
                for i in range(20):
                    if 'jobid' not in SaliWebServiceRunner._waited_jobs:
                        break
                    time.sleep(0.05)
                res = SaliWebServiceRunner._check_completed(url, d.tmpdir)
                self.assertEqual(len(res), 2)
                state = open(os.path.join(d.tmpdir, 'job-state')).read()
                self.assertEqual(state, 'DONE')
        finally:
            saliweb.web_service = old
            saliweb.backend._SaliWebJobWaiter._start_interval = oldin

if __name__ == '__main__':
    unittest.main()
