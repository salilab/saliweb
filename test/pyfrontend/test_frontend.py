from __future__ import print_function
import unittest
import saliweb.frontend
import datetime
import functools
import flask


class Tests(unittest.TestCase):
    """Check frontend"""

    def test_exceptions(self):
        """Check exceptions"""
        bad_job = saliweb.frontend._ResultsBadJobError()
        self.assertEqual(bad_job.http_status, 400)

        gone_job = saliweb.frontend._ResultsGoneError()
        self.assertEqual(gone_job.http_status, 410)

        running_job = saliweb.frontend._ResultsStillRunningError()
        self.assertEqual(running_job.http_status, 503)

    def test_format_timediff(self):
        """Check _format_timediff"""
        _format_timediff = saliweb.frontend._format_timediff
        def tm(**kwargs):
            # Add 0.3 seconds to account for the slightly different value of
            # utcnow between setup and when we call format_timediff
            return (datetime.datetime.utcnow()
                    + datetime.timedelta(microseconds=300, **kwargs))

        # Empty time
        self.assertEqual(_format_timediff(None), None)
        # Time in the past
        self.assertEqual(_format_timediff(tm(seconds=-100)), None)

        self.assertEqual(_format_timediff(tm(seconds=100)), "100 seconds")
        self.assertEqual(_format_timediff(tm(minutes=10)), "10 minutes")
        self.assertEqual(_format_timediff(tm(hours=3)), "3 hours")
        self.assertEqual(_format_timediff(tm(days=100)), "100 days")

    def test_queued_job(self):
        """Test _QueuedJob object"""
        q = saliweb.frontend._QueuedJob({'foo': 'bar', 'name': 'testname',
                                         'submit_time': 'testst',
                                         'state': 'teststate'})
        self.assertEqual(q.name, 'testname')
        self.assertEqual(q.submit_time, 'testst')
        self.assertEqual(q.state, 'teststate')
        self.assertFalse(hasattr(q, 'foo'))

    def test_check_email_required(self):
        """Test check_email with required=True"""
        tf = functools.partial(saliweb.frontend.check_email, required=True)
        self.assertRaises(saliweb.frontend.InputValidationError,
                          tf, None)
        self.assertRaises(saliweb.frontend.InputValidationError,
                          tf, '')
        self.assertRaises(saliweb.frontend.InputValidationError,
                          tf, 'garbage')
        tf("test@test.com")

    def test_check_email_optional(self):
        """Test check_email with required=False"""
        tf = functools.partial(saliweb.frontend.check_email, required=False)
        tf(None)
        tf('')
        self.assertRaises(saliweb.frontend.InputValidationError,
                          tf, 'garbage')
        tf("test@test.com")

    def test_check_modeller_key(self):
        """Test check_modeller_key function"""
        self.assertRaises(saliweb.frontend.InputValidationError,
                          saliweb.frontend.check_modeller_key, "garbage")
        self.assertRaises(saliweb.frontend.InputValidationError,
                          saliweb.frontend.check_modeller_key, None)
        saliweb.frontend.check_modeller_key("@MODELLERKEY@")

    def test_get_completed_job(self):
        """Test get_completed_job function"""
        class MockApp(object):
            def __init__(self):
                self.config = {'DATABASE_USER': 'x', 'DATABASE_DB': 'x',
                               'DATABASE_PASSWD': 'x', 'DATABASE_SOCKET': 'x'}
        flask.current_app = MockApp()

        self.assertRaises(saliweb.frontend._ResultsGoneError,
                          saliweb.frontend.get_completed_job,
                          'expired-job', 'passwd')
        self.assertRaises(saliweb.frontend._ResultsStillRunningError,
                          saliweb.frontend.get_completed_job,
                          'running-job', 'passwd')
        self.assertRaises(saliweb.frontend._ResultsBadJobError,
                          saliweb.frontend.get_completed_job,
                          'bad-job', 'passwd')
        j = saliweb.frontend.get_completed_job('completed-job', 'passwd')

        flask.current_app = None


if __name__ == '__main__':
    unittest.main()
