import unittest
import time
import os
import sys
import saliweb.backend
import saliweb.backend.events
from saliweb.backend.sge import _DRMAAJobWaiter, _SGETasks, _DRMAAWrapper
import testutil

class SGETest(unittest.TestCase):
    """Check SGE utility classes"""

    def test_sge_tasks_none(self):
        """Check the _SGETasks class with no subtasks"""
        for s in ('', '-o foo -p bar'):
            t = _SGETasks(s)
            self.assertTrue(not t)

    def test_sge_tasks_invalid(self):
        """Check the _SGETasks class with invalid input"""
        for s in ('-t ', '-t x:y', '-t FOO'):
            self.assertRaises(ValueError, _SGETasks, s)

    def test_sge_tasks_valid(self):
        """Check the _SGETasks class with valid input"""
        t = _SGETasks('-t 27')
        self.assertEqual((t.first, t.last, t.step), (27, 27, 1))
        t = _SGETasks('-t 4-10')
        self.assertEqual((t.first, t.last, t.step), (4, 10, 1))
        t = _SGETasks('-t 4-10:2')
        self.assertEqual((t.first, t.last, t.step), (4, 10, 2))

    def test_sge_tasks_run_get(self):
        """Check the _SGETasks.get_run_id() method"""
        t = _SGETasks('-t 4-10:2')
        self.assertEqual(t.get_run_id(['foo.4', 'foo.6', 'foo.8', 'foo.10']),
                         'foo.4-10:2')
        t = _SGETasks('-t 1-3')
        self.assertEqual(t.get_run_id(['foo.1', 'foo.2', 'foo.3']),
                         'foo.1-3:1')
        t = _SGETasks('-t 4-10:2')
        self.assertRaises(ValueError, t.get_run_id,
                          ['foo.1', 'foo.2', 'foo.3'])

    def test_drmaa_waiter(self):
        """Check the _DRMAAJobWaiter class"""
        events = []
        class DummyWebService(object):
            def __init__(self):
                self._event_queue = saliweb.backend.events._EventQueue()
        class DummyJobList(object):
            def add(self, key):
                events.append('add job dict ' + key)
            def remove(self, key):
                events.append('remove job dict ' + key)
        class DummyDRMAAModule(object):
            def __init__(self):
                class Dummy(object): pass
                self.Session = Dummy()
                self.Session.TIMEOUT_WAIT_FOREVER = 'forever'
        class DummyDRMAASession(object):
            def synchronize(self, jobids, timeout, cleanup):
                events.append('sync %s timeout %s cleanup %s' \
                              % (str(jobids), timeout, str(cleanup)))
            def wait(self, jobid, timeout):
                events.append('wait %s timeout %s' \
                              % (str(jobid), timeout))
                return jobid != 'jobN.fail'
        class DummyRunner(object):
            _waited_jobs = DummyJobList()
            @classmethod
            def _get_drmaa(cls):
                events.append('get drmaa')
                return DummyDRMAAModule(), DummyDRMAASession()

        ws = DummyWebService()
        runner = DummyRunner()
        w = _DRMAAJobWaiter(ws, ['jobN.1', 'jobN.2'], runner, 'jobN.1-2:1')
        w.start()
        # Give thread time to run (should finish more or less instantly)
        time.sleep(0.1)
        e = ws._event_queue.get(timeout=0.)
        self.assertEqual(e.runid, 'jobN.1-2:1')
        self.assertIsNone(e.run_exception)
        self.assertEqual(events,
                ['add job dict jobN.1-2:1', 'get drmaa',
                 "sync ['jobN.1', 'jobN.2'] timeout forever cleanup False",
                 "wait jobN.1 timeout forever",
                 "wait jobN.2 timeout forever",
                 'remove job dict jobN.1-2:1'])
        events[:] = []

        w = _DRMAAJobWaiter(ws, ['jobN.1', 'jobN.fail'], runner, 'jobN.1-2:1')
        w.start()
        # Give thread time to run (should finish more or less instantly)
        time.sleep(0.1)
        e = ws._event_queue.get(timeout=0.)
        self.assertEqual(e.runid, 'jobN.1-2:1')
        self.assertIsInstance(e.run_exception, saliweb.backend.RunnerError)
        self.assertEqual(events,
                ['add job dict jobN.1-2:1', 'get drmaa',
                 "sync ['jobN.1', 'jobN.fail'] timeout forever cleanup False",
                 "wait jobN.1 timeout forever",
                 "wait jobN.fail timeout forever",
                 'remove job dict jobN.1-2:1'])

    def test_drmaa_wrapper(self):
        """Check the _DRMAAWrapper class"""
        events = []
        class DummyDRMAA(object):
            class Session(object):
                def initialize(self):
                    events.append('drmaa session init')
                def exit(self):
                    events.append('drmaa session exit')
        sys.modules['drmaa'] = DummyDRMAA()
        d = _DRMAAWrapper({})
        self.assertEqual(d.module, sys.modules['drmaa'])
        self.assertIsInstance(d.session, DummyDRMAA.Session)
        self.assertEqual(events, ['drmaa session init'])
        del d
        self.assertEqual(events, ['drmaa session init', 'drmaa session exit'])

        # Destructor should not clean up session if the pointer is lost
        events[:] = []
        d = _DRMAAWrapper({})
        del d.session
        del d
        self.assertEqual(events, ['drmaa session init'])

        # Make sure the environment is cleared of SGE stuff
        os.environ['SGE_FOO'] = 'bar'
        d = _DRMAAWrapper({'SGE_BAR': 'foo'})
        self.assertEqual(os.environ['SGE_BAR'], 'foo')
        self.assertNotIn('SGE_FOO', os.environ)
        del sys.modules['drmaa']

if __name__ == '__main__':
    unittest.main()
