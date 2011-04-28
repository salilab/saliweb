import unittest
import time
import os
import socket
import saliweb.backend.events

class EventsTest(unittest.TestCase):
    """Check events"""

    def test_event_queue(self):
        """Check the _EventQueue class"""
        e = saliweb.backend.events._EventQueue()
        self.assertEqual(e.get(0), None)
        e.put('a')
        e.put('b')
        self.assertEqual(e.get(), 'a')
        self.assertEqual(e.get(), 'b')
        self.assertEqual(e.get(0), None)

    def test_incoming_jobs_event(self):
        """Check the _IncomingJobsEvent class"""
        class dummy:
            def _process_incoming_jobs(self): self.processed = True
        d = dummy()
        e = saliweb.backend.events._IncomingJobsEvent(d)
        e.process()
        self.assertEqual(d.processed, True)

    def test_cleanup_incoming_jobs_event(self):
        """Check the _CleanupIncomingJobsEvent class"""
        class dummy:
            def _cleanup_incoming_jobs(self): self.processed = True
        d = dummy()
        e = saliweb.backend.events._CleanupIncomingJobsEvent(d)
        e.process()
        self.assertEqual(d.processed, True)

    def test_old_jobs_event(self):
        """Check the _OldJobsEvent class"""
        class dummy:
            def _process_old_jobs(self): self.processed = True
        d = dummy()
        e = saliweb.backend.events._OldJobsEvent(d)
        e.process()
        self.assertEqual(d.processed, True)

    def test_completed_job_event(self):
        """Check the _CompletedJobEvent class"""
        class DummyJob(object):
            def _try_complete(self, webservice, run_exception):
                webservice.run_exception = run_exception
        class DummyWebService(object):
            def _get_job_by_runner_id(self, runner, runid):
                if runid == 'bad':
                    return None
                else:
                    return DummyJob()

        ws = DummyWebService()
        ev = saliweb.backend.events._CompletedJobEvent(ws, None, 'good', None)
        ev.process()
        self.assertEqual(ws.run_exception, None)

        ws = DummyWebService()
        ev = saliweb.backend.events._CompletedJobEvent(ws, None, 'good', 'foo')
        ev.process()
        self.assertEqual(ws.run_exception, 'foo')

        ws = DummyWebService()
        ev = saliweb.backend.events._CompletedJobEvent(ws, None, 'bad', 'foo')
        ev.process()
        # try_complete should not be called if the job ID does not exist
        self.assertEqual(hasattr(ws, 'run_exception'), False)

    def test_old_jobs(self):
        """Check the _OldJobs class"""
        class dummy:
            def _get_oldjob_interval(self): return 0.02
        q = saliweb.backend.events._EventQueue()
        ws = dummy()
        ws._event_queue = q
        t = saliweb.backend.events._OldJobs(ws)
        t.start()
        time.sleep(0.05)
        # Should have added 2 events
        for i in range(2):
            x = q.get(timeout=0.)
            self.assert_(isinstance(x, saliweb.backend.events._OldJobsEvent))
        self.assertEqual(q.get(timeout=0.), None)

    def test_cleanup_incoming_jobs(self):
        """Check the _CleanupIncomingJobs class"""
        class dummy:
            def _get_cleanup_incoming_job_times(self): return (0.02, 0.02)
        q = saliweb.backend.events._EventQueue()
        ws = dummy()
        ws._event_queue = q
        t = saliweb.backend.events._CleanupIncomingJobs(ws)
        t.start()
        time.sleep(0.05)
        # Should have added 2 events
        for i in range(2):
            x = q.get(timeout=0.)
            self.assert_(isinstance(x,
                         saliweb.backend.events._CleanupIncomingJobsEvent))
        self.assertEqual(q.get(timeout=0.), None)

    def test_incoming_jobs(self):
        """Check the _IncomingJobs class"""
        class dummy: pass
        ws = dummy()
        ws.config = dummy()
        ws.config.backend = {'check_minutes':1}

        if os.path.exists('test.sock'):
            os.unlink('test.sock')
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind('test.sock')
        sock.listen(5)

        q = saliweb.backend.events._EventQueue()
        ws._event_queue = q
        t = saliweb.backend.events._IncomingJobs(ws, sock)
        t.start()
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect('test.sock')
        s.send("new job")
        time.sleep(0.05)
        # Should have added 1 event
        x = q.get(timeout=0.)
        self.assert_(isinstance(x, saliweb.backend.events._IncomingJobsEvent))
        self.assertEqual(q.get(timeout=0.), None)

        ws.config.backend = {'check_minutes':0.02/60.0}
        q = saliweb.backend.events._EventQueue()
        ws._event_queue = q
        t = saliweb.backend.events._IncomingJobs(ws, sock)
        t.start()
        time.sleep(0.05)
        # Should have added 2 events
        for i in range(2):
            x = q.get(timeout=0.)
            self.assert_(isinstance(x,
                                    saliweb.backend.events._IncomingJobsEvent))
        self.assertEqual(q.get(timeout=0.), None)
        os.unlink('test.sock')

if __name__ == '__main__':
    unittest.main()
