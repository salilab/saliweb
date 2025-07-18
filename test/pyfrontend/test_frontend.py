import unittest
import saliweb.frontend
import datetime
import functools
import contextlib
import os
import gzip
import tempfile
import struct
import ihm.format_bcif
import flask


def _utcnow():
    """Get the current UTC time and date"""
    # MySQLdb uses naive datetime objects. We store all dates in the DB
    # in UTC. This function replaces datetime.datetime.utcnow() as that has
    # been deprecated in modern Python.
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


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


def _add_msgpack(d, fh):
    """Add `d` to filelike object `fh` in msgpack format"""
    if isinstance(d, dict):
        fh.write(struct.pack('>Bi', 0xdf, len(d)))
        for key, val in d.items():
            _add_msgpack(key, fh)
            _add_msgpack(val, fh)
    elif isinstance(d, list):
        fh.write(struct.pack('>Bi', 0xdd, len(d)))
        for val in d:
            _add_msgpack(val, fh)
    elif isinstance(d, str):
        b = d.encode('utf8')
        fh.write(struct.pack('>Bi', 0xdb, len(b)))
        fh.write(b)
    elif isinstance(d, bytes):
        fh.write(struct.pack('>Bi', 0xc6, len(d)))
        fh.write(d)
    elif isinstance(d, int):
        fh.write(struct.pack('>Bi', 0xce, d))
    elif d is None:
        fh.write(b'\xc0')
    else:
        raise TypeError("Cannot handle %s" % type(d))


def make_test_pdb(tmpdir):
    os.mkdir(os.path.join(tmpdir, 'xy'))
    with gzip.open(os.path.join(tmpdir, 'xy', 'pdb1xyz.ent.gz'), 'wt') as fh:
        fh.write("REMARK  6  TEST REMARK\n")
        fh.write("ATOM      1  N   ALA C   1      27.932  14.488   4.257  "
                 "1.00 23.91           N\n")
        fh.write("ATOM      1  N   ALA D   1      27.932  14.488   4.257  "
                 "1.00 23.91           N\n")


def make_test_mmcif(tmpdir, ihm=False):
    if ihm:
        os.mkdir(os.path.join(tmpdir, 'zz'))
        os.mkdir(os.path.join(tmpdir, 'zz', '1zza'))
        os.mkdir(os.path.join(tmpdir, 'zz', '1zza', 'structures'))
        fname = os.path.join(tmpdir, 'zz', '1zza', 'structures', '1zza.cif.gz')
    else:
        os.mkdir(os.path.join(tmpdir, 'xy'))
        fname = os.path.join(tmpdir, 'xy', '1xyz.cif.gz')

    with gzip.open(fname, 'wt') as fh:
        fh.write("""
loop_
_atom_site.group_PDB
_atom_site.type_symbol
_atom_site.label_atom_id
_atom_site.label_alt_id
_atom_site.label_comp_id
_atom_site.label_asym_id
_atom_site.auth_asym_id
_atom_site.label_seq_id
_atom_site.auth_seq_id
_atom_site.pdbx_PDB_ins_code
_atom_site.Cartn_x
_atom_site.Cartn_y
_atom_site.Cartn_z
_atom_site.occupancy
_atom_site.B_iso_or_equiv
_atom_site.label_entity_id
_atom_site.id
_atom_site.pdbx_PDB_model_num
ATOM N N . ALA A C 1 1 ? 27.932 14.488 4.257 1.000 23.91 1 1 1
ATOM N N . ALA B D 1 1 ? 27.932 14.488 4.257 1.000 23.91 1 2 1
""")


class Tests(unittest.TestCase):
    """Check frontend"""

    def test_exceptions(self):
        """Check exceptions"""
        bad_job = saliweb.frontend._ResultsBadJobError()
        self.assertEqual(bad_job.http_status, 400)

        gone_job = saliweb.frontend._ResultsGoneError()
        self.assertEqual(gone_job.http_status, 410)

        running_job = saliweb.frontend._ResultsStillRunningError(
            "testmsg", "testjob", "testtemplate")
        self.assertEqual(running_job.http_status, 503)
        self.assertEqual(str(running_job), 'testmsg')
        self.assertEqual(running_job.job, 'testjob')
        self.assertEqual(running_job.template, 'testtemplate')

    def test_format_timediff(self):
        """Check _format_timediff"""
        _format_timediff = saliweb.frontend._format_timediff

        def tm(**kwargs):
            # Add 0.3 seconds to account for the slightly different value of
            # utcnow between setup and when we call format_timediff
            return (_utcnow() + datetime.timedelta(microseconds=300, **kwargs))

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
        rd = {'email': 'testemail', 'first_name': 'foo', 'last_name': 'bar',
              'institution': 'testin', 'modeller_key': 'modkey'}
        flask.g.user = saliweb.frontend.LoggedInUser('testuser', rd)
        self.assertEqual(str(q.name_link), '<a href="testurl">testname</a>')
        del flask.g.user

    def test_check_cluster_running(self):
        """Test _check_cluster_running function"""
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_job = os.path.join(tmpdir, 'job1')
            run_job = os.path.join(tmpdir, 'job2')
            os.mkdir(queue_job)
            os.mkdir(run_job)
            with open(os.path.join(run_job, 'job-state'), 'w'):
                pass
            # Queued job, should be changed to QUEUED
            j = {'state': 'RUNNING', 'directory': queue_job}
            jnew = saliweb.frontend._check_cluster_running(j)
            self.assertEqual(jnew['state'], 'QUEUED')

            # Job really is running, should be unchanged
            j = {'state': 'RUNNING', 'directory': run_job}
            jnew = saliweb.frontend._check_cluster_running(j)
            self.assertEqual(jnew, j)

            # Completed job, should be unchanged
            j = {'state': 'COMPLETED'}
            jnew = saliweb.frontend._check_cluster_running(j)
            self.assertEqual(jnew, j)

    def test_completed_job(self):
        """Test _CompletedJob object"""
        j = saliweb.frontend.CompletedJob({'foo': 'bar', 'name': 'testname',
                                           'passwd': 'testpw',
                                           'archive_time': 'testar',
                                           'directory': 'testdir',
                                           'contact_email': 'test@test.com'})
        self.assertEqual(j.name, 'testname')
        self.assertEqual(j.passwd, 'testpw')
        self.assertEqual(j.archive_time, 'testar')
        self.assertEqual(j.directory, 'testdir')
        self.assertEqual(j.email, 'test@test.com')
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
        j.archive_time = (_utcnow() + datetime.timedelta(days=5, hours=1))
        self.assertEqual(str(j.get_results_available_time()),
                         '<p>Job results will be available at this URL '
                         'for 5 days.</p>')
        self.assertEqual(j.get_path('foo.log'), 'testdir/foo.log')

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

    def test_check_pdb(self):
        """Test check_pdb"""
        with tempfile.TemporaryDirectory() as tmpdir:
            good_pdb = os.path.join(tmpdir, 'good.pdb')
            with open(good_pdb, 'w') as fh:
                fh.write("REMARK  6  TEST REMARK\n")
                fh.write(
                    "ATOM      1  N   ALA C   1      27.932  14.488   4.257  "
                    "1.00 23.91           N\n")
            bad_pdb = os.path.join(tmpdir, 'bad.pdb')
            with open(bad_pdb, 'w') as fh:
                fh.write("not a pdb\n")
            # Use .pdb file extension but actually contain mmCIF data
            good_cif = os.path.join(tmpdir, 'goodcif.pdb')
            with open(good_cif, 'w') as fh:
                fh.write("loop_\n_atom_site.group_PDB\nATOM\nATOM\n")

            saliweb.frontend.check_pdb(good_pdb)
            saliweb.frontend.check_pdb(good_pdb, show_filename='good.pdb')
            saliweb.frontend.check_pdb_or_mmcif(good_pdb)
            self.assertRaises(saliweb.frontend.InputValidationError,
                              saliweb.frontend.check_pdb, bad_pdb)
            self.assertRaises(saliweb.frontend.InputValidationError,
                              saliweb.frontend.check_pdb, bad_pdb,
                              show_filename='bad.pdb')
            self.assertRaises(saliweb.frontend.InputValidationError,
                              saliweb.frontend.check_pdb_or_mmcif, bad_pdb)
            self.assertRaises(saliweb.frontend.InputValidationError,
                              saliweb.frontend.check_pdb, good_cif)
            # check_pdb_or_mmcif should fail on a good cif too since it
            # should treat it as a PDB file based on the .pdb file extension
            self.assertRaises(saliweb.frontend.InputValidationError,
                              saliweb.frontend.check_pdb_or_mmcif, good_cif)
            # Should pass though if forced to treat it as mmCIF
            saliweb.frontend.check_mmcif(good_cif)

    def test_check_mmcif(self):
        """Test check_mmcif"""
        with tempfile.TemporaryDirectory() as tmpdir:
            good_cif = os.path.join(tmpdir, 'good.cif')
            with open(good_cif, 'w') as fh:
                fh.write("loop_\n_atom_site.group_PDB\nATOM\nATOM\n")
            bad_cif = os.path.join(tmpdir, 'bad.cif')
            with open(bad_cif, 'w') as fh:
                fh.write("not an mmCIF\n")

            saliweb.frontend.check_mmcif(good_cif)
            saliweb.frontend.check_mmcif(good_cif, show_filename='good.cif')
            saliweb.frontend.check_pdb_or_mmcif(good_cif)
            self.assertRaises(saliweb.frontend.InputValidationError,
                              saliweb.frontend.check_mmcif, bad_cif)
            self.assertRaises(saliweb.frontend.InputValidationError,
                              saliweb.frontend.check_mmcif, bad_cif,
                              show_filename='bad.cif')
            self.assertRaises(saliweb.frontend.InputValidationError,
                              saliweb.frontend.check_pdb_or_mmcif, bad_cif)

    def test_check_bcif(self):
        """Test check_bcif"""
        c = {'name': 'Cartn_x',
             'mask': None,
             'data': {'data': struct.pack('<2d', 1.0, 2.0),
                      'encoding':
                      [{'kind': 'ByteArray',
                        'type': ihm.format_bcif._Float64}]}}
        d = {'dataBlocks': [{'categories': [{'name': '_atom_site',
                                             'columns': [c]}]}]}

        with tempfile.TemporaryDirectory() as tmpdir:
            good_bcif = os.path.join(tmpdir, 'good.bcif')
            with open(good_bcif, 'wb') as fh:
                _add_msgpack(d, fh)
            bad_bcif = os.path.join(tmpdir, 'bad.bcif')
            with open(bad_bcif, 'w') as fh:
                fh.write('garbage')
            saliweb.frontend.check_bcif(good_bcif)
            saliweb.frontend.check_bcif(good_bcif, show_filename='good.bcif')
            self.assertRaises(saliweb.frontend.InputValidationError,
                              saliweb.frontend.check_bcif, bad_bcif)
            self.assertRaises(saliweb.frontend.InputValidationError,
                              saliweb.frontend.check_bcif, bad_bcif,
                              show_filename='bad.bcif')

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
        try:
            saliweb.frontend.get_completed_job('running-job', 'passwd')
        except saliweb.frontend._ResultsStillRunningError as err:
            # Test the StillRunningJob object returned
            j = err.job
        self.assertEqual(j.name, 'running-job')
        self.assertEqual(j.email, 'test@test.com')
        self.assertEqual(j.get_refresh_time(1000), 1000)
        # Test job claims to be submitted 10 seconds ago, so result should
        # be approximately that
        self.assertAlmostEqual(j.get_refresh_time(1), 10, delta=1.0)

        self.assertRaises(saliweb.frontend._ResultsBadJobError,
                          saliweb.frontend.get_completed_job,
                          'bad-job', 'passwd')
        j = saliweb.frontend.get_completed_job('completed-job', 'passwd')
        self.assertEqual(j.email, 'test@test.com')

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
        rd = {'email': 'testemail', 'first_name': 'foo', 'last_name': 'bar',
              'institution': 'testin', 'modeller_key': 'modkey'}
        u = saliweb.frontend.LoggedInUser('foo', rd)
        self.assertEqual(u.name, 'foo')
        self.assertEqual(u.email, 'testemail')
        self.assertEqual(u.first_name, 'foo')
        self.assertEqual(u.last_name, 'bar')
        self.assertEqual(u.institution, 'testin')
        self.assertEqual(u.modeller_key, 'modkey')
        rd['modeller_key'] = None
        u = saliweb.frontend.LoggedInUser('foo', rd)
        self.assertEqual(u.modeller_key, '')

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
                                           'directory': 'testdir',
                                           'contact_email': None})
        with request_mime_type('text/html'):
            r = saliweb.frontend.render_results_template('results.html', job=j)
            self.assertTrue(r.startswith('render results.html with ()'))

    def test_render_results_template_xml(self):
        """Test render_results_template function (XML)"""
        j = saliweb.frontend.CompletedJob({'foo': 'bar', 'name': 'testname',
                                           'passwd': 'testpw',
                                           'archive_time': 'testar',
                                           'directory': 'testdir',
                                           'contact_email': None})
        with request_mime_type('application/xml'):
            r = saliweb.frontend.render_results_template('results.html', job=j)
            self.assertTrue(r.startswith('render saliweb/results.xml with ()'))

    def test_render_results_template_xml_extra(self):
        """Test render_results_template function (XML, with extra files)"""
        j = saliweb.frontend.CompletedJob({'foo': 'bar', 'name': 'testname',
                                           'passwd': 'testpw',
                                           'archive_time': 'testar',
                                           'directory': 'testdir',
                                           'contact_email': None})
        with request_mime_type('application/xml'):
            r = saliweb.frontend.render_results_template(
                'results.html', job=j,
                extra_xml_outputs=['foo', 'bar'],
                extra_xml_metadata={'baz': 'bazval'},
                extra_xml_links={'link': 'lnkval'})
            self.assertTrue(r.startswith('render saliweb/results.xml with ()'))
            self.assertEqual([r['fname'] for r in j._record_results],
                             ['foo', 'bar'])

    def test_read_config(self):
        """Test _read_config function"""
        config_template = """
[general]
service_name: test_service

[database]
frontend_config: frontend.conf
db: test_db
%s

[directories]
install: test_install
"""

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
        with tempfile.TemporaryDirectory() as tmpdir:
            fname = os.path.join(tmpdir, 'live.conf')
            with open(fname, 'w') as fh:
                fh.write(config_template % "")
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

            with open(fname, 'w') as fh:
                fh.write(config_template % "socket: /foo/bar")
            saliweb.frontend._read_config(app, fname)
            self.assertEqual(app.config['DATABASE_SOCKET'], '/foo/bar')

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

    def test_make_application(self):
        """Test make_application function"""
        import mock_application  # noqa: F401

        class MockAccept(object):
            def __init__(self, mime):
                self.mime = mime

            def best_match(self, types):
                return self.mime if self.mime in types else None

            def __getitem__(self, key):
                return 1.0 if key == self.mime else 0.0

        class MockRequest(object):
            def __init__(self, scheme, mime):
                self.scheme = scheme
                self.cookies = {}
                self.accept_mimetypes = MockAccept(mime)
        # Logins have to be SSL-secured
        flask.request = MockRequest(scheme='https', mime='text/html')

        with tempfile.TemporaryDirectory() as tmpdir:
            fname = os.path.join(tmpdir, 'live.conf')
            os.environ['MOCK_APPLICATION_CONFIG'] = fname
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
            os.environ['MOCK_APPLICATION_VERSION'] = '1.0'
            f = saliweb.frontend.make_application("mock_application")
            # Now check the Flask handlers
            for h in f.before_request_handlers:
                h()
            for h in f.teardown_app_handlers:
                h('noerror')
            for h in f.teardown_request_handlers:
                h('noerror')
            # Check teardown with no database handle
            del flask.g.db_conn
            for h in f.teardown_app_handlers:
                h('noerror')
            # Test cleanup of incoming jobs
            indir = os.path.join(tmpdir, 'incoming-dir')

            class MockIncomingJob(object):
                directory = indir

                def __init__(self, submitted):
                    self._submitted = submitted
            flask.g.incoming_jobs = [MockIncomingJob(True),
                                     MockIncomingJob(False)]
            for h in f.teardown_request_handlers:
                h('noerror')
            del flask.g.incoming_jobs
            # Test internal error handler
            out = f.error_handlers[500]('MockError')
            self.assertEqual(
                out,
                ('render saliweb/internal_error.html with (), {}', 500))
            # Test results error handler
            err = saliweb.frontend._ResultsGoneError("foo")
            out = f.error_handlers[saliweb.frontend._ResultsError](err)
            self.assertEqual(
                out,
                ("render saliweb/results_error.html with (), "
                 "{'message': 'foo'}", 410))
            # Test job-still-running error handler
            err = saliweb.frontend._ResultsStillRunningError(
                "foo", "testjob", "testtemplate")
            out = f.error_handlers[
                         saliweb.frontend._ResultsStillRunningError](err)
            self.assertIn("render testtemplate with ()", out[0])
            self.assertEqual(out[1], 503)
            # Test XML output
            flask.request.accept_mimetypes.mime = 'application/xml'
            out = f.error_handlers[
                         saliweb.frontend._ResultsStillRunningError](err)
            self.assertIn("render saliweb/results_error.xml", out[0])
            self.assertEqual(out[1], 503)
            flask.request.accept_mimetypes.mime = 'text/html'
            # Test user error handler
            err = saliweb.frontend.InputValidationError("foo")
            out = f.error_handlers[saliweb.frontend._UserError](err)
            self.assertEqual(
                out, ("render saliweb/user_error.html with (), "
                      "{'message': 'foo'}", 400))
            # Test access-denied error handler
            err = saliweb.frontend.AccessDeniedError("foo")
            out = f.error_handlers[saliweb.frontend.AccessDeniedError](err)
            self.assertEqual(
                out, ("render saliweb/access_denied_error.html with (), "
                      "{'message': 'foo'}", 401))
        del flask.request

    def test_get_pdb_code(self):
        """Test get_pdb_code function"""
        class MockApp(object):
            def __init__(self, tmpdir):
                self.config = {'PDB_ROOT': os.path.join(tmpdir, 'pdb'),
                               'MMCIF_ROOT': os.path.join(tmpdir, 'mmCIF'),
                               'IHM_ROOT': os.path.join(tmpdir, 'ihm')}
        with tempfile.TemporaryDirectory() as tmpdir:
            pdb_dir = os.path.join(tmpdir, 'pdb')
            mmcif_dir = os.path.join(tmpdir, 'mmCIF')
            ihm_dir = os.path.join(tmpdir, 'ihm')
            os.mkdir(pdb_dir)
            os.mkdir(mmcif_dir)
            os.mkdir(ihm_dir)
            make_test_pdb(pdb_dir)
            make_test_mmcif(mmcif_dir)
            make_test_mmcif(ihm_dir, ihm=True)
            flask.current_app = MockApp(tmpdir)
            self.assertRaises(saliweb.frontend.InputValidationError,
                              saliweb.frontend.get_pdb_code, "1@bc", tmpdir)
            with self.assertRaises(
                    saliweb.frontend.InputValidationError) as cm:
                saliweb.frontend.get_pdb_code("1aaaaaa", tmpdir)
            self.assertEqual(str(cm.exception),
                             "PDB code '1aaaaaa' does not exist in our copy "
                             "of the PDB database.")
            self.assertFalse(saliweb.frontend.pdb_code_exists('1aaaaaa'))
            self.assertRaises(
                ValueError, saliweb.frontend.pdb_code_exists, '1xyz',
                formats=['not-pdb'])
            self.assertTrue(saliweb.frontend.pdb_code_exists(
                '1xyz', formats=['PDB']))
            self.assertTrue(saliweb.frontend.pdb_code_exists(
                '1xyz', formats=['MMCIF']))
            # Check in IHM directory structure
            self.assertTrue(saliweb.frontend.pdb_code_exists(
                '1zza', formats=['IHM']))
            p = saliweb.frontend.get_pdb_code('1xyz', tmpdir)
            self.assertEqual(p, os.path.join(tmpdir, 'pdb1xyz.ent'))
            p = saliweb.frontend.get_pdb_code(
                '1xyz', tmpdir, formats=['PDB', 'MMCIF'])
            self.assertEqual(p, os.path.join(tmpdir, 'pdb1xyz.ent'))
            os.unlink(os.path.join(tmpdir, 'pdb1xyz.ent'))

            p = saliweb.frontend.get_pdb_code(
                '1xyz', tmpdir, formats=['MMCIF', 'PDB'])
            self.assertEqual(p, os.path.join(tmpdir, '1xyz.cif'))
            os.unlink(os.path.join(tmpdir, '1xyz.cif'))
            flask.current_app = None

    def test_get_pdb_chains(self):
        """Test get_pdb_chains function"""
        class MockApp(object):
            def __init__(self, tmpdir):
                self.config = {'PDB_ROOT': os.path.join(tmpdir, 'pdb'),
                               'MMCIF_ROOT': os.path.join(tmpdir, 'mmCIF')}
        with tempfile.TemporaryDirectory() as tmpdir:
            pdb_dir = os.path.join(tmpdir, 'pdb')
            mmcif_dir = os.path.join(tmpdir, 'mmCIF')
            os.mkdir(pdb_dir)
            os.mkdir(mmcif_dir)
            make_test_pdb(pdb_dir)
            make_test_mmcif(mmcif_dir)
            flask.current_app = MockApp(tmpdir)
            # No chains specified, PDB
            p = saliweb.frontend.get_pdb_chains('1xyz', tmpdir)
            self.assertEqual(p, os.path.join(tmpdir, 'pdb1xyz.ent'))
            os.unlink(os.path.join(tmpdir, 'pdb1xyz.ent'))

            # No chains specified, mmCIF
            p = saliweb.frontend.get_pdb_chains('1xyz', tmpdir,
                                                formats=['MMCIF'])
            self.assertEqual(p, os.path.join(tmpdir, '1xyz.cif'))
            os.unlink(os.path.join(tmpdir, '1xyz.cif'))

            # "-" chain requested, PDB
            p = saliweb.frontend.get_pdb_chains('1xyz:-', tmpdir,
                                                formats=['PDB'])
            self.assertEqual(p, os.path.join(tmpdir, 'pdb1xyz.ent'))
            os.unlink(os.path.join(tmpdir, 'pdb1xyz.ent'))

            # "-" chain requested, mmCIF
            p = saliweb.frontend.get_pdb_chains('1xyz:-', tmpdir,
                                                formats=['MMCIF'])
            self.assertEqual(p, os.path.join(tmpdir, '1xyz.cif'))
            os.unlink(os.path.join(tmpdir, '1xyz.cif'))

            # Invalid chain requested
            self.assertRaises(saliweb.frontend.InputValidationError,
                              saliweb.frontend.get_pdb_chains, "1xyz:\t",
                              tmpdir)
            self.assertFalse(
                os.path.exists(os.path.join(tmpdir, 'pdb1xyz.ent')))
            self.assertRaises(saliweb.frontend.InputValidationError,
                              saliweb.frontend.get_pdb_chains, "1xyz:\t",
                              tmpdir, formats=['MMCIF'])
            self.assertFalse(
                os.path.exists(os.path.join(tmpdir, '1xyz.cif')))

            # One chain (E) not in PDB
            self.assertRaises(saliweb.frontend.InputValidationError,
                              saliweb.frontend.get_pdb_chains, "1xyz:C,D,E",
                              tmpdir)
            self.assertFalse(
                os.path.exists(os.path.join(tmpdir, 'pdb1xyz.ent')))
            self.assertFalse(
                os.path.exists(os.path.join(tmpdir, 'pdb1xyzCDE.ent')))
            self.assertRaises(saliweb.frontend.InputValidationError,
                              saliweb.frontend.get_pdb_chains, "1xyz:C,D,E",
                              tmpdir, formats=['MMCIF'])
            self.assertFalse(
                os.path.exists(os.path.join(tmpdir, '1xyz.cif')))
            self.assertFalse(
                os.path.exists(os.path.join(tmpdir, '1xyzCDE.cif')))

            # Multiple chains (E,F) not in PDB
            self.assertRaises(saliweb.frontend.InputValidationError,
                              saliweb.frontend.get_pdb_chains, "1xyz:C,D,E,F",
                              tmpdir)
            self.assertRaises(saliweb.frontend.InputValidationError,
                              saliweb.frontend.get_pdb_chains, "1xyz:C,D,E,F",
                              tmpdir, formats=['MMCIF'])

            # Two-character chain not present in PDB
            self.assertRaises(saliweb.frontend.InputValidationError,
                              saliweb.frontend.get_pdb_chains, "1xyz:CD",
                              tmpdir)
            self.assertRaises(saliweb.frontend.InputValidationError,
                              saliweb.frontend.get_pdb_chains, "1xyz:CD",
                              tmpdir, formats=['MMCIF'])

            # One OK chain requested, PDB
            p = saliweb.frontend.get_pdb_chains('1xyz:C', tmpdir)
            self.assertFalse(
                os.path.exists(os.path.join(tmpdir, 'pdb1xyz.ent')))
            outf = os.path.join(tmpdir, '1xyzC.pdb')
            self.assertEqual(p, outf)
            self._check_pdb_chains(outf, ['C'])
            os.unlink(outf)

            # One OK chain requested, mmCIF
            p = saliweb.frontend.get_pdb_chains('1xyz:C', tmpdir,
                                                formats=['MMCIF'])
            self.assertFalse(
                os.path.exists(os.path.join(tmpdir, '1xyz.cif')))
            outf = os.path.join(tmpdir, '1xyzC.cif')
            self.assertEqual(p, outf)
            self._check_mmcif_chains(outf, ['C'])
            os.unlink(outf)

            # Two OK chains requested, PDB
            p = saliweb.frontend.get_pdb_chains('1xyz:C,D', tmpdir)
            self.assertFalse(
                os.path.exists(os.path.join(tmpdir, 'pdb1xyz.ent')))
            outf = os.path.join(tmpdir, '1xyzCD.pdb')
            self.assertEqual(p, outf)
            self._check_pdb_chains(outf, ['C', 'D'])
            os.unlink(outf)

            # Two OK chains requested, mmCIF
            p = saliweb.frontend.get_pdb_chains('1xyz:C,D', tmpdir,
                                                formats=['MMCIF'])
            self.assertFalse(
                os.path.exists(os.path.join(tmpdir, '1xyz.cif')))
            outf = os.path.join(tmpdir, '1xyzCD.cif')
            self.assertEqual(p, outf)
            self._check_mmcif_chains(outf, ['C', 'D'])
            os.unlink(outf)

            flask.current_app = None

    def _check_pdb_chains(self, fname, exp_chains):
        """Assert that the PDB file contains exactly the given chains"""
        def yield_chains(fh):
            for line in fh:
                if line.startswith('HETATM') or line.startswith('ATOM'):
                    yield line[21]
        with open(fname) as fh:
            chains = frozenset(yield_chains(fh))
        self.assertEqual(chains, frozenset(exp_chains))

    def _check_mmcif_chains(self, fname, exp_chains):
        """Assert that the mmCIF file contains exactly the given chains"""
        def yield_chains(fh):
            for line in fh:
                if line.startswith('HETATM') or line.startswith('ATOM'):
                    yield line.split()[14]
        with open(fname) as fh:
            chains = frozenset(yield_chains(fh))
        self.assertEqual(chains, frozenset(exp_chains))


if __name__ == '__main__':
    unittest.main()
