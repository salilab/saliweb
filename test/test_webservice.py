import unittest
import os
import re
import datetime
import tempfile
import time
import sys
from test_database import make_test_jobs
from memory_database import MemoryDatabase
from config import Config
from saliweb.backend import WebService, Job, StateFileError, SanityError
import saliweb.backend
from StringIO import StringIO
from testutil import RunInTempDir

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
        self.assertEqual(ws.version, None)
        # OK to make multiple WebService instances
        ws2 = WebService(conf, db)

    def test_get_job_by_name(self):
        """Check WebService.get_job_by_name()"""
        db, conf, web = self._setup_webservice()
        job = web.get_job_by_name('RUNNING', 'job3')
        self.assertEqual(job.name, 'job3')
        job = web.get_job_by_name('RUNNING', 'job9')
        self.assertEqual(job, None)

    def test_get_job_by_runner_id(self):
        """Check WebService._get_job_by_runner_id()"""
        db, conf, web = self._setup_webservice()
        goodrunner = saliweb.backend.SaliSGERunner('foo')
        badrunner = saliweb.backend.LocalRunner('foo')
        job = web._get_job_by_runner_id(goodrunner, 'job-2')
        self.assertEqual(job.name, 'job2')
        job = web._get_job_by_runner_id(badrunner, 'job-2')
        self.assertEqual(job, None)
        job = web._get_job_by_runner_id(goodrunner, 'job-3')
        self.assertEqual(job, None)

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
        except TestFatalError, detail:
            # handler should reraise error
            self.assertRaises(TestFatalError, web._handle_fatal_error, detail)
        # WebService should leave a state file to prevent further
        # processes from running
        x = open('state_file').read().rstrip('\r\n')
        os.unlink('state_file')
        self.assert_(re.search('FAILED: Traceback.*fatal error to be handled',
                               x, flags=re.DOTALL),
                     'Unexpected failure message: ' + x)
        mail = conf.get_mail_output()
        self.assert_(re.search('Subject: .*From: testadmin.*To: testadmin' \
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
        # sanity check should check PREPROCESSING and POSTPROCESSING jobs
        self.assertEqual(job_log, [('preproc', 'sanity_check'),
                                   ('postproc', 'sanity_check')])

    def test_filesystem_sanity_check(self):
        """Check WebService._filesystem_sanity_check()"""
        t = RunInTempDir()
        db, conf, web = self._setup_webservice(t.tmpdir)
        # Fail if job directories do not exist
        self.assertRaises(SanityError, web._filesystem_sanity_check)
        # Make job directories
        os.mkdir('incoming')
        os.mkdir('preprocessing')
        # Garbage files not in job directories are fine
        open('garbage-file', 'w').write('test')
        web._filesystem_sanity_check()

    def test_filesystem_sanity_check_garbage_files(self):
        """Check WebService._filesystem_sanity_check() with garbage files"""
        t = RunInTempDir()
        os.mkdir('incoming')
        os.mkdir('preprocessing')
        db, conf, web = self._setup_webservice(t.tmpdir)
        web._filesystem_sanity_check()
        # Make files (not directories) in job directories
        open('incoming/garbage-file', 'w').write('test')
        self.assertRaises(SanityError, web._filesystem_sanity_check)

    def test_filesystem_sanity_check_garbage_dirs(self):
        """Check WebService._filesystem_sanity_check() with garbage dirs"""
        t = RunInTempDir()
        os.mkdir('incoming')
        os.mkdir('preprocessing')
        db, conf, web = self._setup_webservice(t.tmpdir)
        web._filesystem_sanity_check()
        # Make extra directories in job directories
        os.mkdir('incoming/garbage-job')
        self.assertRaises(SanityError, web._filesystem_sanity_check)

    def test_filesystem_sanity_check_badjobdir(self):
        """Check WebService._filesystem_sanity_check() with bad job dir"""
        t = RunInTempDir()
        os.mkdir('incoming')
        os.mkdir('preprocessing')
        db, conf, web = self._setup_webservice(t.tmpdir)
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

    def test_cleanup_incoming_jobs(self):
        """Test WebSerivce._cleanup_incoming_jobs() method"""
        cleaned_dirs = []
        def _cleanup_dir(dir, age):
            cleaned_dirs.append((dir, age))
        t = RunInTempDir()
        os.mkdir('incoming')
        os.mkdir('preprocessing')
        db, conf, web = self._setup_webservice(t.tmpdir)
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
        self.assert_(cleaned_dirs[0][0].endswith('/incoming/badjob'))
        self.assertEqual(cleaned_dirs[0][1], 3600.)
        # Cleanup of zero directories should also work
        web._cleanup_incoming_jobs()

    def test_cleanup_dir(self):
        """Test WebService._cleanup_dir() method"""
        if isinstance(os.stat("/tmp").st_mtime, int):
            sys.stderr.write("test skipped: stat does not have "
                             "subsecond granularity: ")
            return
        t = RunInTempDir()
        os.mkdir('incoming')
        os.mkdir('preprocessing')
        db, conf, web = self._setup_webservice(t.tmpdir)
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
        self.assert_(not os.path.exists("dir1"))
        self.assert_(os.path.exists("dir2"))
        self.assert_(os.path.exists("dir3"))

        # Cleanup of non-existent directory should be OK
        web._cleanup_dir("baddir", 0.05)

if __name__ == '__main__':
    unittest.main()
