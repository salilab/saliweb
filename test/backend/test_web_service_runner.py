import unittest
import os
from saliweb.backend import SaliWebServiceRunner
import saliweb
import saliweb.backend.events
from test_make_web_service import RunInTempDir

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
            d = RunInTempDir()
            r = SaliWebServiceRunner('testurl', ['arg1', 'arg2'])
            os.chdir(d.origdir)
            url = r._run(ws)
            self.assertEqual(url, 'jobid')
            event1 = ws._event_queue.get()
            res = SaliWebServiceRunner._check_completed(url, d.tmpdir)
            self.assertEqual(len(res), 2)
            d = open(os.path.join(d.tmpdir, 'job-state')).read()
            self.assertEqual(d, 'DONE')
        finally:
            saliweb.web_service = old
            saliweb.backend._SaliWebJobWaiter._start_interval = oldin

if __name__ == '__main__':
    unittest.main()
