import unittest
import socket
import os
import re
import datetime
import tempfile
import time
import sys
import contextlib
from test_database import make_test_jobs
from memory_database import MemoryDatabase
from config import Config
from saliweb.backend import WebService, Job, StateFileError, SanityError
import saliweb.backend
if sys.version_info[0] >= 3:
    from io import StringIO
else:
    from io import BytesIO as StringIO
import testutil

basic_config = """
[general]
admin_email: testadmin@salilab.org
service_name: test_service
socket: test.socket

[backend]
user: test
state_file: state_file
check_minutes: 10

[database]
db: testdb
frontend_config: frontend.conf
backend_config: backend.conf

[directories]
install: /
incoming: %(directory)s/incoming
preprocessing: %(directory)s/preprocessing

[oldjobs]
archive: 30d
expire: 90d
"""

class TestFatalError(Exception): pass

job_log = []
class LoggingJob(Job):
    """Test Job subclass that logs which methods are called"""
    def _try_run(self, webservice):
        if self.name == 'fatal-error-run':
            raise TestFatalError("fatal error in run")
        job_log.append((self.name, 'run'))
    def _try_complete(self, webservice): job_log.append((self.name, 'complete'))
    def _try_archive(self): job_log.append((self.name, 'archive'))
    def _try_expire(self): job_log.append((self.name, 'expire'))
    def _sanity_check(self): job_log.append((self.name, 'sanity_check'))


@contextlib.contextmanager
def mock_setfacl(tmpdir, fail=False):
    setfacl = os.path.join(tmpdir, 'setfacl')
    with open(setfacl, 'w') as fh:
        fh.write('#!/bin/bash\n')
        fh.write('exit %d\n' % (1 if fail else 0))
    os.chmod(setfacl, 0o700)
    orig_path = os.environ['PATH']
    os.environ['PATH'] = tmpdir + ':' + os.environ['PATH']
    yield
    os.environ['PATH'] = orig_path


class WebServiceTest(unittest.TestCase):
    """Check WebService class"""

    def _setup_webservice(self, directory='/'):
        db = MemoryDatabase(LoggingJob)
        conf = Config(StringIO(basic_config % {'directory': directory}))
        web = WebService(conf, db)
        web.create_database_tables()
        make_test_jobs(db.conn)
        return db, conf, web

    def test_init(self):
        """Check WebService init"""
        db = MemoryDatabase(Job)
        conf = Config(StringIO(basic_config % {'directory': '/'}))
        ws = WebService(conf, db)
        self.assertIsNone(ws.version)
        # OK to make multiple WebService instances
        ws2 = WebService(conf, db)
        # Test with hostname tracking
        conf.track_hostname = True
        ws3 = WebService(conf, db)

    def test_get_oldjob_interval(self):
        """Check WebService._get_oldjob_interval()"""
        db = MemoryDatabase(Job)
        conf = Config(StringIO(basic_config % {'directory': '/'}))
        ws = WebService(conf, db)
        self.assertEqual(ws._get_oldjob_interval(), 259200)

    def test_make_close_socket(self):
        """Check WebService make and close socket"""
        db = MemoryDatabase(Job)
        conf = Config(StringIO(basic_config % {'directory': '/'}))
        with testutil.temp_dir() as tmpdir:
            sockfile = os.path.join(tmpdir, 'test.socket')
            conf.socket = sockfile
            ws = WebService(conf, db)
            with mock_setfacl(tmpdir, fail=True):
                self.assertRaises(OSError, ws._make_socket)
            with mock_setfacl(tmpdir):
                sock = ws._make_socket()
            ws._close_socket(sock)

    def test_register(self):
        """Check WebService._register()"""
        db, conf, web = self._setup_webservice()
        # Exceptions should be swallowed if the socket does not exist
        web._system_socket_file = '/does/not/exist'
        web._register(True)
        web._register(False)

        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            os.unlink('test-socket')
        except OSError:
            pass
        s.bind('test-socket')
        s.listen(5)

        db, conf, web = self._setup_webservice()
        web.config.directories['install'] = '/test/install'
        web._system_socket_file = 'test-socket'
        web._register(True)
        web._register(False)

        up, addr = s.accept()
        self.assertEqual(up.recv(4096), b'1/test/install/bin/service.py')

        down, addr = s.accept()
        self.assertEqual(down.recv(4096), b'0/test/install/bin/service.py')

        s.close()
        del s
        os.unlink('test-socket')

    def test_get_job_by_name(self):
        """Check WebService.get_job_by_name()"""
        db, conf, web = self._setup_webservice()
        job = web.get_job_by_name('RUNNING', 'job3')
        self.assertEqual(job.name, 'job3')
        job = web.get_job_by_name('RUNNING', 'job9')
        self.assertIsNone(job)

    def test_get_job_by_runner_id(self):
        """Check WebService._get_job_by_runner_id()"""
        db, conf, web = self._setup_webservice()
        goodrunner = saliweb.backend.SaliSGERunner('foo')
        badrunner = saliweb.backend.LocalRunner('foo')
        job = web._get_job_by_runner_id(goodrunner, 'job-2')
        self.assertEqual(job.name, 'job2')
        job = web._get_job_by_runner_id(badrunner, 'job-2')
        self.assertIsNone(job)
        job = web._get_job_by_runner_id(goodrunner, 'job-3')
        self.assertIsNone(job)

    def test_process_incoming(self):
        """Check WebService._process_incoming_jobs()"""
        global job_log
        job_log = []
        db, conf, web = self._setup_webservice()
        web._check_state_file()
        web._process_incoming_jobs()
        self.assertEqual(job_log, [('job1', 'run')])
        # Only a single WebService can process jobs concurrently
        ws2 = WebService(conf, db)
        self.assertRaises(StateFileError, ws2._check_state_file)

    def test_incoming_depends(self):
        """Check that incoming jobs honor dependencies"""
        global job_log
        job_log = []
        db, conf, web = self._setup_webservice()
        c = db.conn.cursor()
        query = "INSERT INTO dependencies(child,parent) VALUES(?,?)"
        c.execute(query, ('job1', 'job2'))
        db.conn.commit()

        web._process_incoming_jobs()
        # job1 should not run because it depends on job2
        self.assertEqual(job_log, [])

    def test_max_running(self):
        """Make sure that limits.running is honored"""
        global job_log
        def setup_two_incoming(running):
            global job_log
            job_log = []
            db, conf, web = self._setup_webservice()
            conf.limits['running'] = running
            c = db.conn.cursor()
            c.execute("INSERT INTO jobs(name,state,submit_time, "
                      "directory,url) VALUES(?,?,?,?,?)",
                      ('injob2', 'INCOMING', datetime.datetime.utcnow(),
                       '/', 'http://testurl'))
            db.conn.commit()
            return db, conf, web

        # No jobs should be run if the limit is already met
        db, conf, web = setup_two_incoming(2)
        web._process_incoming_jobs()
        self.assertEqual(job_log, [])

        # Both incoming jobs should be run if the limit permits it
        db, conf, web = setup_two_incoming(10)
        web._process_incoming_jobs()
        self.assertEqual(job_log, [('job1', 'run'), ('injob2', 'run')])

        # Only one incoming job should be run if the limit is reached
        db, conf, web = setup_two_incoming(3)
        web._process_incoming_jobs()
        self.assertEqual(job_log, [('job1', 'run')])

    def test_fatal_error_propagated(self):
        """Make sure that fatal errors are propagated"""
        db, conf, web = self._setup_webservice()
        c = db.conn.cursor()
        c.execute("INSERT INTO jobs(name,state,submit_time, " \
                  + "directory,url) VALUES(?,?,?,?,?)",
                 ('fatal-error-run', 'INCOMING', datetime.datetime.utcnow(),
                  '/', 'http://testurl'))
        db.conn.commit()
        # Error is not handled by Job, so should be propagated by WebService
        self.assertRaises(TestFatalError, web._process_incoming_jobs)

    def test_handle_fatal_error(self):
        """Check WebService handling of fatal job errors"""
        db, conf, web = self._setup_webservice()
        try:
            raise TestFatalError("fatal error to be handled")
        except TestFatalError as detail:
            # handler should reraise error
            self.assertRaises(TestFatalError, web._handle_fatal_error, detail)
        # WebService should leave a state file to prevent further
        # processes from running
        with open('state_file') as fh:
            x = fh.read().rstrip('\r\n')
        os.unlink('state_file')
        self.assertTrue(
                re.search('FAILED: Traceback.*fatal error to be handled',
                          x, flags=re.DOTALL),
                'Unexpected failure message: ' + x)
        mail = conf.get_mail_output()
        self.assertTrue(re.search('Subject: .*From: testadmin.*To: testadmin' \
                               + '.*Traceback.*test_handle_fatal_error.*' \
                               + 'TestFatalError: fatal error to be handled',
                               mail, flags=re.DOTALL),
                     'Unexpected mail output: ' + mail)

    def test_process_completed(self):
        """Check WebService._process_completed_jobs()"""
        global job_log
        job_log = []
        db, conf, web = self._setup_webservice()
        web._process_completed_jobs()
        self.assertEqual(job_log, [('job2', 'complete'), ('job3', 'complete')])

    def test_process_old(self):
        """Check WebService._process_old_jobs()"""
        global job_log
        job_log = []
        db, conf, web = self._setup_webservice()
        web._process_old_jobs()
        self.assertEqual(job_log, [(u'ready-for-archive', 'archive'),
                                   (u'ready-for-expire', 'expire')])

    def test_all_processing(self):
        """Check WebService.do_all_processing()"""
        global job_log
        job_log = []
        db, conf, web = self._setup_webservice()
#       web.do_all_processing()
#       self.assertEqual(job_log, [('job1', 'run'),
#                                  ('job2', 'complete'), ('job3', 'complete'),
#                                  (u'ready-for-archive', 'archive'),
#                                  (u'ready-for-expire', 'expire')])

    def test_job_sanity_check(self):
        """Check WebService._job_sanity_check()"""
        global job_log
        job_log = []
        db, conf, web = self._setup_webservice()
        web._job_sanity_check()
        # sanity check should check PREPROCESSING, POSTPROCESSING, and
        # FINALIZING jobs
        self.assertEqual(job_log, [('preproc', 'sanity_check'),
                                   ('postproc', 'sanity_check'),
                                   ('finalize', 'sanity_check')])

    @testutil.run_in_tempdir
    def test_get_running_pid(self):
        """Check WebService.get_running_pid()"""
        db, conf, web = self._setup_webservice('.')
        # No state file -> return None
        self.assertIsNone(web.get_running_pid())
        # FAILED state file -> raise error
        with open('state_file', 'w') as fh:
            fh.write('FAILED: error\n')
        self.assertRaises(StateFileError, web.get_running_pid)
        # Running pid -> return it
        ourpid = os.getpid()
        with open('state_file', 'w') as fh:
            fh.write('%d' % ourpid)
        self.assertEqual(web.get_running_pid(), ourpid)
        # Non-running pid -> return None
        # Unlikely to have a real pid this large!
        with open('state_file', 'w') as fh:
            fh.write('99999999')
        self.assertIsNone(web.get_running_pid())

    @testutil.run_in_tempdir
    def test_filesystem_sanity_check(self):
        """Check WebService._filesystem_sanity_check()"""
        db, conf, web = self._setup_webservice('.')
        # Fail if job directories do not exist
        self.assertRaises(SanityError, web._filesystem_sanity_check)
        # Make job directories
        os.mkdir('incoming')
        os.mkdir('preprocessing')
        # Garbage files not in job directories are fine
        with open('garbage-file', 'w') as fh:
            fh.write('test')
        web._filesystem_sanity_check()

    @testutil.run_in_tempdir
    def test_filesystem_sanity_check_garbage_files(self):
        """Check WebService._filesystem_sanity_check() with garbage files"""
        os.mkdir('incoming')
        os.mkdir('preprocessing')
        db, conf, web = self._setup_webservice('.')
        web._filesystem_sanity_check()
        # Make files (not directories) in job directories
        with open('incoming/garbage-file', 'w') as fh:
            fh.write('test')
        self.assertRaises(SanityError, web._filesystem_sanity_check)

    @testutil.run_in_tempdir
    def test_filesystem_sanity_check_garbage_dirs(self):
        """Check WebService._filesystem_sanity_check() with garbage dirs"""
        os.mkdir('incoming')
        os.mkdir('preprocessing')
        db, conf, web = self._setup_webservice('.')
        web._filesystem_sanity_check()
        # Make extra directories in job directories
        os.mkdir('incoming/garbage-job')
        self.assertRaises(SanityError, web._filesystem_sanity_check)

    @testutil.run_in_tempdir
    def test_filesystem_sanity_check_badjobdir(self):
        """Check WebService._filesystem_sanity_check() with bad job dir"""
        os.mkdir('incoming')
        os.mkdir('preprocessing')
        db, conf, web = self._setup_webservice('.')
        web._filesystem_sanity_check()
        # Make job with non-existing directory
        c = db.conn.cursor()
        utcnow = datetime.datetime.utcnow()
        c.execute("INSERT INTO jobs(name,state,runner_id,submit_time, " \
                  + "expire_time,directory,url) VALUES(?,?,?,?,?,?,?)",
                  ('badjobdir', 'INCOMING', 'SGE-job-1', utcnow,
                  utcnow + datetime.timedelta(days=1), '/not/exist',
                  'http://testurl'))
        db.conn.commit()
        self.assertRaises(SanityError, web._filesystem_sanity_check)

    @testutil.run_in_tempdir
    def test_filesystem_sanity_check_nojobdir(self):
        """Check WebService._filesystem_sanity_check() with no job dir"""
        os.mkdir('incoming')
        os.mkdir('preprocessing')
        db, conf, web = self._setup_webservice('.')
        web._filesystem_sanity_check()
        # Make job with non-existing directory
        c = db.conn.cursor()
        utcnow = datetime.datetime.utcnow()
        c.execute("INSERT INTO jobs(name,state,runner_id,submit_time, " \
                  + "expire_time,directory,url) VALUES(?,?,?,?,?,?,?)",
                  ('badjobdir', 'INCOMING', 'SGE-job-1', utcnow,
                  utcnow + datetime.timedelta(days=1), None,
                  'http://testurl'))
        db.conn.commit()
        self.assertRaises(SanityError, web._filesystem_sanity_check)

    @testutil.run_in_tempdir
    def test_cleanup_incoming_jobs(self):
        """Test WebSerivce._cleanup_incoming_jobs() method"""
        cleaned_dirs = []
        def _cleanup_dir(dir, age):
            cleaned_dirs.append((dir, age))
        os.mkdir('incoming')
        os.mkdir('preprocessing')
        db, conf, web = self._setup_webservice('.')
        # Make directory with no corresponding job database row
        os.mkdir('incoming/badjob')
        # Make job with non-existing directory
        c = db.conn.cursor()
        utcnow = datetime.datetime.utcnow()
        c.execute("INSERT INTO jobs(name,state,runner_id,submit_time, " \
                  + "expire_time,directory,url) VALUES(?,?,?,?,?,?,?)",
                  ('badjobdir', 'INCOMING', 'SGE-job-1', utcnow,
                  utcnow + datetime.timedelta(days=1), '/not/exist',
                  'http://testurl'))
        db.conn.commit()
        web._cleanup_dir = _cleanup_dir
        web._cleanup_incoming_jobs()
        self.assertEqual(len(cleaned_dirs), 1)
        self.assertTrue(cleaned_dirs[0][0].endswith('/incoming/badjob'))
        self.assertEqual(cleaned_dirs[0][1], 3600.)
        # Cleanup of zero directories should also work
        web._cleanup_incoming_jobs()

    @testutil.run_in_tempdir
    def test_cleanup_dir(self):
        """Test WebService._cleanup_dir() method"""
        if isinstance(os.stat("/tmp").st_mtime, int):
            sys.stderr.write("test skipped: stat does not have "
                             "subsecond granularity: ")
            return
        os.mkdir('incoming')
        os.mkdir('preprocessing')
        db, conf, web = self._setup_webservice('.')
        os.mkdir('dir1')
        os.mkdir('dir2')
        time.sleep(0.02)
        os.mkdir('dir2/subdir')
        time.sleep(0.02)
        os.mkdir('dir3')
        time.sleep(0.02)
        # Only dir1 should be cleaned, since dir3 is too recent, and
        # dir2 has a recently-added child
        web._cleanup_dir("dir1", 0.05)
        web._cleanup_dir("dir2", 0.05)
        web._cleanup_dir("dir3", 0.05)
        self.assertFalse(os.path.exists("dir1"))
        self.assertTrue(os.path.exists("dir2"))
        self.assertTrue(os.path.exists("dir3"))

        # Cleanup of non-existent directory should be OK
        web._cleanup_dir("baddir", 0.05)

    def test_periodic_actions(self):
        """Test WebService._do_periodic_actions() method"""
        threads = []
        events = []
        class DummyEvent(object):
            def __init__(self, name):
                self.name = name
            def process(self):
                events.append(self.name)
        queue = [None, DummyEvent('foo'), DummyEvent('bar'), None]
        class DummyWebService(WebService):
            def __init__(self):
                pass
        def make_thread(name):
            class DummyThread(object):
                def __init__(self, *args):
                    pass
                def start(self):
                    threads.append(name)
            return DummyThread
        class DummyEvents(object):
            class _EventQueue(object):
                def get(self, timeout):
                    return queue.pop()
        e = DummyEvents()
        for t in ['_PeriodicCheck', '_IncomingJobs', '_OldJobs',
                  '_CleanupIncomingJobs']:
            setattr(e, t, make_thread(t))
        oldev = saliweb.backend.events
        w = DummyWebService()
        try:
            saliweb.backend.events = e
            # queue is finite, so will hit the end eventually (IndexError)
            self.assertRaises(IndexError, w._do_periodic_actions, None)
            self.assertEqual(threads, ['_PeriodicCheck', '_IncomingJobs',
                                       '_OldJobs', '_CleanupIncomingJobs'])
            self.assertEqual(events, ['bar', 'foo'])
        finally:
            saliweb.backend.events = oldev


if __name__ == '__main__':
    unittest.main()
