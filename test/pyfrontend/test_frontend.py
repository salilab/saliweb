from __future__ import print_function
import unittest
import saliweb.frontend
import datetime
import functools
import contextlib
import os
import util
import flask


@contextlib.contextmanager
def request_mime_type(mime):
    """Temporarily set the HTTP Accept header"""
    class MockAccept(object):
        def best_match(self, types):
            return mime if mime in types else None
        def __getitem__(self, key):
            return 1.0 if key == mime else 0.0
    class MockRequest(object):
        def __init__(self):
            self.accept_mimetypes = MockAccept()
    flask.request = MockRequest()
    yield
    del flask.request


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
                                         'state': 'teststate',
                                         'user': 'testuser',
                                         'url': 'testurl'})
        self.assertEqual(q.name, 'testname')
        self.assertEqual(q.submit_time, 'testst')
        self.assertEqual(q.state, 'teststate')
        self.assertEqual(q.user, 'testuser')
        self.assertEqual(q.url, 'testurl')
        self.assertFalse(hasattr(q, 'foo'))
        flask.g.user = None
        self.assertEqual(q.name_link, 'testname')
        flask.g.user = saliweb.frontend.LoggedInUser(name='testuser',
                                                     email='testemail')
        self.assertEqual(str(q.name_link), '<a href="testurl">testname</a>')
        del flask.g.user

    def test_completed_job(self):
        """Test _CompletedJob object"""
        j = saliweb.frontend.CompletedJob({'foo': 'bar', 'name': 'testname',
                                           'passwd': 'testpw',
                                           'archive_time': 'testar',
                                           'directory': 'testdir'})
        self.assertEqual(j.name, 'testname')
        self.assertEqual(j.passwd, 'testpw')
        self.assertEqual(j.archive_time, 'testar')
        self.assertEqual(j.directory, 'testdir')
        self.assertFalse(hasattr(j, 'foo'))
        self.assertTrue(j.get_results_file_url('foo')
                        .startswith('results_file;()'))
        self.assertEqual(j._record_results, None)
        j._record_results = []
        self.assertTrue(j.get_results_file_url('foo')
                        .startswith('https://results_file;()'))
        self.assertEqual(len(j._record_results), 1)
        self.assertEqual(j._record_results[0]['fname'], 'foo')
        self.assertTrue(j._record_results[0]['url']
                        .startswith('https://results_file;()'))
        j.archive_time = None
        self.assertEqual(j.get_results_available_time(), None)
        j.archive_time = (datetime.datetime.utcnow()
                          + datetime.timedelta(days=5, hours=1))
        self.assertEqual(str(j.get_results_available_time()),
                         '<p>Job results will be available at this URL '
                         'for 5 days.</p>')

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
        class MockApp(object):
            def __init__(self):
                self.config = {'MODELLER_LICENSE_KEY': '@MODELLERKEY@'}
        flask.current_app = MockApp()
        self.assertRaises(saliweb.frontend.InputValidationError,
                          saliweb.frontend.check_modeller_key, "garbage")
        self.assertRaises(saliweb.frontend.InputValidationError,
                          saliweb.frontend.check_modeller_key, None)
        saliweb.frontend.check_modeller_key("@MODELLERKEY@")
        flask.current_app = None

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

    def test_get_servers_cookie_info(self):
        """Test _get_servers_cookie_info function"""
        class MockRequest(object):
            def __init__(self):
                self.cookies = {}
        flask.request = MockRequest()
        c = saliweb.frontend._get_servers_cookie_info()
        self.assertEqual(c, None)

        flask.request.cookies['sali-servers'] = 'foo&bar&bar&baz'
        c = saliweb.frontend._get_servers_cookie_info()
        self.assertEqual(c, {'foo': 'bar', 'bar': 'baz'})
        del flask.request

    def test_logged_in_user(self):
        """Test LoggedInUser class"""
        u = saliweb.frontend.LoggedInUser(name='foo', email='bar')
        self.assertEqual(u.name, 'foo')
        self.assertEqual(u.email, 'bar')

    def test_get_logged_in_user(self):
        """Test _get_logged_in_user function"""
        class MockRequest(object):
            def __init__(self, scheme):
                self.scheme = scheme
                self.cookies = {}
            def set_servers_cookie(self, d):
                c = '&'.join('%s&%s' % x for x in d.items())
                self.cookies['sali-servers'] = c

        # Logins have to be SSL-secured
        flask.request = MockRequest(scheme='http')
        u = saliweb.frontend._get_logged_in_user()
        self.assertEqual(u, None)

        # No logged-in user
        flask.request = MockRequest(scheme='https')
        u = saliweb.frontend._get_logged_in_user()
        self.assertEqual(u, None)

        # Anonymous user
        flask.request = MockRequest(scheme='https')
        flask.request.set_servers_cookie({'user_name': 'Anonymous',
                                          'session': 'pwcrypt'})
        u = saliweb.frontend._get_logged_in_user()
        self.assertEqual(u, None)

        # User with wrong password
        flask.request = MockRequest(scheme='https')
        flask.request.set_servers_cookie({'user_name': 'testuser',
                                          'session': 'badpwcrypt'})
        u = saliweb.frontend._get_logged_in_user()
        self.assertEqual(u, None)

        # User with correct password
        flask.request = MockRequest(scheme='https')
        flask.request.set_servers_cookie({'user_name': 'testuser',
                                          'session': 'goodpwcrypt'})
        u = saliweb.frontend._get_logged_in_user()
        self.assertEqual(u.name, 'testuser')
        self.assertEqual(u.email, 'testemail')

        del flask.request

    def test_parameters(self):
        """Test Parameter and FileParameter classes"""
        p = saliweb.frontend.Parameter("foo", "bar")
        self.assertEqual(p._name, 'foo')
        self.assertEqual(p._description, 'bar')
        self.assertEqual(p._xml_type, 'string')
        self.assertFalse(p._optional)

        p = saliweb.frontend.Parameter("foo", "bar", optional=True)
        self.assertTrue(p._optional)

        p = saliweb.frontend.FileParameter("foo", "bar")
        self.assertEqual(p._xml_type, 'file')

    def test_request_wants_xml(self):
        """Test _request_wants_xml function"""
        with request_mime_type('text/html'):
            self.assertFalse(saliweb.frontend._request_wants_xml())

        with request_mime_type('application/xml'):
            self.assertTrue(saliweb.frontend._request_wants_xml())

    def test_render_queue_page_html(self):
        """Test render_queue_page (HTML)"""
        with request_mime_type('text/html'):
            r = saliweb.frontend.render_queue_page()
            self.assertTrue(r.startswith('render saliweb/queue.html'))

    def test_render_queue_page_xml(self):
        """Test render_queue_page (XML)"""
        with request_mime_type('application/xml'):
            r = saliweb.frontend.render_queue_page()
            self.assertTrue(r.startswith('render saliweb/help.xml'))

    def test_render_results_template_html(self):
        """Test render_results_template function (HTML)"""
        j = saliweb.frontend.CompletedJob({'foo': 'bar', 'name': 'testname',
                                           'passwd': 'testpw',
                                           'archive_time': 'testar',
                                           'directory': 'testdir'})
        with request_mime_type('text/html'):
            r = saliweb.frontend.render_results_template('results.html', job=j)
            self.assertTrue(r.startswith('render results.html with ()'))

    def test_render_results_template_xml(self):
        """Test render_results_template function (XML)"""
        j = saliweb.frontend.CompletedJob({'foo': 'bar', 'name': 'testname',
                                           'passwd': 'testpw',
                                           'archive_time': 'testar',
                                           'directory': 'testdir'})
        with request_mime_type('application/xml'):
            r = saliweb.frontend.render_results_template('results.html', job=j)
            self.assertTrue(r.startswith('render saliweb/results.xml with ()'))

    def test_read_config(self):
        """Test _read_config function"""
        class MockConfig(object):
            def __init__(self):
                self.d = {}
            def __setitem__(self, key, value):
                self.d[key] = value
            def __getitem__(self, key):
                return self.d[key]
            def __contains__(self, key):
                return key in self.d
            def from_object(self, obj):
                pass
     
        class MockApp(object):
            def __init__(self):
                self.config = MockConfig()
        app = MockApp()
        with util.temporary_directory() as tmpdir:
            fname = os.path.join(tmpdir, 'live.conf')
            with open(fname, 'w') as fh:
                fh.write("""
[general]
service_name: test_service

[database]
frontend_config: frontend.conf
db: test_db

[directories]
install: test_install
""")
            fe_config = os.path.join(tmpdir, 'frontend.conf')
            with open(fe_config, 'w') as fh:
                fh.write("""
[frontend_db]
user: test_fe_user
passwd: test_fe_pwd
""")
            saliweb.frontend._read_config(app, fname)
            self.assertEqual(app.config['DATABASE_SOCKET'],
                             '/var/lib/mysql/mysql.sock')
            self.assertEqual(app.config['DATABASE_DB'], 'test_db')
            self.assertEqual(app.config['DATABASE_USER'], 'test_fe_user')
            self.assertEqual(app.config['DATABASE_PASSWD'], 'test_fe_pwd')
            self.assertEqual(app.config['DIRECTORIES_INSTALL'], 'test_install')
            self.assertEqual(app.config['SERVICE_NAME'], 'test_service')

    def test_setup_email_logging(self):
        """Test _setup_email_logging function"""
        class MockLogger(object):
            def __init__(self):
                self.handlers = []
            def addHandler(self, h):
                self.handlers.append(h)
        class MockApp(object):
            def __init__(self, debug):
                self.debug = debug
                self.config = {'SERVICE_NAME': 'test_service',
                               'ADMIN_EMAIL': 'test_admin'}
                self.logger = MockLogger()

        app = MockApp(debug=True)
        saliweb.frontend._setup_email_logging(app)
        self.assertEqual(len(app.logger.handlers), 0)

        app = MockApp(debug=False)
        saliweb.frontend._setup_email_logging(app)
        self.assertEqual(len(app.logger.handlers), 1)


if __name__ == '__main__':
    unittest.main()
