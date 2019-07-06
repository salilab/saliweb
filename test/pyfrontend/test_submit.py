from __future__ import print_function
import flask
import unittest
import os
import re
from saliweb.frontend import submit
import saliweb.frontend
import util


class Tests(unittest.TestCase):
    """Check job submission"""

    def test_sanitize_job_name(self):
        """Check _sanitize_job_name function"""
        self.assertEqual(submit._sanitize_job_name("ABC&^abc; 123_-X"),
                         "ABCabc123_-X")

        self.assertEqual(submit._sanitize_job_name(
            "012345678901234567890123456789abcdefghijlk"),
            "012345678901234567890123456789")

        self.assertEqual(submit._sanitize_job_name(None), "job")
        self.assertEqual(submit._sanitize_job_name(""), "job")

    def test_generate_random_password(self):
        """Test _generate_random_password function"""
        self.assertEqual(len(submit._generate_random_password(10)), 10)
        self.assertEqual(len(submit._generate_random_password(20)), 20)

    def test_get_trial_job_names(self):
        """Test _get_trial_job_names"""
        names = list(submit._get_trial_job_names("testjob"))
        self.assertEqual(names[0], 'testjob')
        self.assertTrue(re.match('testjob_\d+\.0$', names[1]))
        self.assertTrue(re.match('testjob_\d+\.1$', names[2]))

    def test_try_job_name(self):
        """Test _try_job_name function"""
        class MockCursor(object):
            def __init__(self):
                self.execute_calls = 0
            def execute(self, sql, args):
                self.jobname = args[0]
                self.execute_calls += 1
            def fetchone(self):
                if self.jobname == 'existing-job':
                    return (1,)
                elif self.jobname == 'justmade-job' and self.execute_calls > 1:
                    return (1,)
                else:
                    return (0,)
        class MockApp(object):
            def __init__(self, tmpdir):
                self.config = {'DIRECTORIES_INCOMING': tmpdir}
        with util.temporary_directory() as tmpdir:
            flask.current_app = MockApp(tmpdir)
            os.mkdir(os.path.join(tmpdir, 'existing-dir'))
            # Cannot create a job if the directory already exists
            cur = MockCursor()
            self.assertEqual(submit._try_job_name("existing-dir", cur), None)
            self.assertEqual(cur.execute_calls, 0)

            # Cannot create a job if the DB has an entry for it already
            cur = MockCursor()
            self.assertEqual(submit._try_job_name("existing-job", cur), None)
            self.assertEqual(cur.execute_calls, 1)

            # Test second DB check after mkdir
            cur = MockCursor()
            self.assertEqual(submit._try_job_name("justmade-job", cur), None)
            self.assertEqual(cur.execute_calls, 2)

            # Test successful job
            cur = MockCursor()
            nm = submit._try_job_name("new-job", cur)
            self.assertTrue(os.path.isdir(nm))
            self.assertEqual(cur.execute_calls, 2)
        flask.current_app = None

    def test_get_job_name_directory(self):
        """Test _get_job_name_directory function"""
        class MockApp(object):
            def __init__(self, tmpdir):
                self.config = {'DATABASE_USER': 'x', 'DATABASE_DB': 'x',
                               'DATABASE_PASSWD': 'x', 'DATABASE_SOCKET': 'x',
                               'DIRECTORIES_INCOMING': tmpdir}
        with util.temporary_directory() as tmpdir:
            flask.current_app = MockApp(tmpdir)
            job_name, job_dir = submit._get_job_name_directory("new_!$job")
            self.assertEqual(job_name, 'new_job')

            # running-job* are in the db; test failure to generate a
            # unique job name
            self.assertRaises(ValueError, submit._get_job_name_directory,
                              "running-job")
        flask.current_app = None


if __name__ == '__main__':
    unittest.main()
