from __future__ import print_function
import flask
import unittest
import os
import socket
import re
from saliweb.frontend import submit
import saliweb.frontend
import contextlib
import util
from test_frontend import request_mime_type


@contextlib.contextmanager
def mock_app(track=False, socket='/not/exist'):
    class MockApp(object):
        def __init__(self, tmpdir, track, socket):
            self.config = {'DATABASE_USER': 'x', 'DATABASE_DB': 'x',
                           'DATABASE_PASSWD': 'x', 'DATABASE_SOCKET': 'x',
                           'DIRECTORIES_INCOMING': tmpdir,
                           'TRACK_HOSTNAME': track, 'SOCKET': socket}
    with util.temporary_directory() as tmpdir:
        flask.current_app = MockApp(tmpdir, track=track, socket=socket)
        yield flask.current_app, tmpdir
        flask.current_app = None


class Tests(unittest.TestCase):
    """Check job submission"""

    def test_sanitize_job_name(self):
        """Check _sanitize_job_name function"""
        self.assertEqual(submit._sanitize_job_name("ABC&^abc; 123_-X"),
                         "ABCabc123_-X")

        self.assertEqual(submit._sanitize_job_name(
            "012345678901234567890123456789abcdefghijlk"),
            "012345678901234567890123456789")

        self.assertEqual(submit._sanitize_job_name(None)[:3], "job")
        self.assertEqual(submit._sanitize_job_name("")[:3], "job")

    def test_generate_random_password(self):
        """Test _generate_random_password function"""
        self.assertEqual(len(submit._generate_random_password(10)), 10)
        self.assertEqual(len(submit._generate_random_password(20)), 20)

    def test_get_trial_job_names(self):
        """Test _get_trial_job_names"""
        names = list(submit._get_trial_job_names("testjob"))
        self.assertEqual(names[0], 'testjob')
        self.assertTrue(re.match(r'testjob_\d+0$', names[1]))
        self.assertTrue(re.match(r'testjob_\d+1$', names[2]))

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
        with mock_app():
            job_name, job_dir = submit._get_job_name_directory("new_!$job")
            self.assertEqual(job_name, 'new_job')

            # running-job* are in the db; test failure to generate a
            # unique job name
            self.assertRaises(ValueError, submit._get_job_name_directory,
                              "running-job")

    def test_generate_results_url(self):
        """Test _generate_results_url function"""
        url, passwd = submit._generate_results_url("testjob")
        self.assertEqual(len(passwd), 10)

    def test_incoming_job(self):
        """Test IncomingJob objects"""
        class MockRequest(object):
            def __init__(self):
                self.remote_addr = None
        with mock_app(track=False) as (app, tmpdir):
            flask.request = MockRequest()
            flask.g.user = None
            j = submit.IncomingJob("test$!job")
            self.assertEqual(j.name, "testjob")
            self.assertEqual(j.directory, os.path.join(tmpdir, "testjob"))
            fname = j.get_path("test")
            self.assertEqual(fname, os.path.join(tmpdir, "testjob", "test"))
            self.assertRaises(ValueError, getattr, j, 'results_url')
            j.submit()
            results_url = j.results_url
            self.assertTrue(results_url.startswith('https://results'))

        with mock_app(track=True) as (app, tmpdir):
            j = submit.IncomingJob("test$!job")
            j.submit()

        # Test with active backend socket
        with util.temporary_directory() as sockdir:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sockpth = os.path.join(sockdir, 'test.socket')
            s.bind(sockpth)
            s.listen(5)
            with mock_app(track=False, socket=sockpth) as (app, tmpdir):
                j = submit.IncomingJob("test$!job")
                j.submit()
            conn, addr = s.accept()
            self.assertEqual(conn.recv(1024), b'INCOMING testjob\n')
            s.close()

    def test_incoming_job_force_xml(self):
        """Test IncomingJob objects with force_results_xml=True"""
        class MockRequest(object):
            def __init__(self):
                self.remote_addr = None
        with mock_app(track=False) as (app, tmpdir):
            flask.request = MockRequest()
            flask.g.user = None
            j = submit.IncomingJob("test$!job")
            j.submit(force_results_xml=True)
            results_url = j.results_url
            self.assertIn("'force_xml': '1'", results_url)

    def test_render_submit_template_html(self):
        """Test render_submit_template (HTML output)"""
        with request_mime_type('text/html'):
            with mock_app(track=False) as (app, tmpdir):
                j = submit.IncomingJob("testjob")
                j.submit()
                r = saliweb.frontend.render_submit_template('results.html',
                                                            job=j)
                self.assertTrue(r.startswith('render results.html with ()'))

    def test_render_submit_template_xml(self):
        """Test render_submit_template (XML output)"""
        with request_mime_type('application/xml'):
            with mock_app(track=False) as (app, tmpdir):
                j = submit.IncomingJob("testjob")
                j.submit()
                r = saliweb.frontend.render_submit_template('results.html',
                                                            job=j)
                self.assertTrue(
                    r.startswith('render saliweb/submit.xml with ()'))

    def test_redirect_to_results_page_html(self):
        """Test redirect_to_results_page (HTML output)"""
        with request_mime_type('text/html'):
            with mock_app(track=False) as (app, tmpdir):
                j = submit.IncomingJob("testjob")
                j.submit()
                r = saliweb.frontend.redirect_to_results_page(j)
                self.assertIn('redirect to results;', r)
                self.assertIn('code 302', r)

    def test_redirect_to_results_page_xml(self):
        """Test redirect_to_results_page (XML output)"""
        with request_mime_type('application/xml'):
            with mock_app(track=False) as (app, tmpdir):
                j = submit.IncomingJob("testjob")
                j.submit()
                r = saliweb.frontend.redirect_to_results_page(j)
                self.assertTrue(
                    r.startswith('render saliweb/submit.xml with ()'))


if __name__ == '__main__':
    unittest.main()
