import unittest
import datetime
import os
import re
import tempfile
from memory_database import MemoryDatabase
from saliweb.backend import WebService, Job, InvalidStateError, Runner
from saliweb.backend import MySQLField
from config import Config
from StringIO import StringIO

Job._state_file_wait_time = 0.01

class DoNothingRunner(Runner):
    _runner_name = 'donothing'
    def __init__(self, id):
        Runner.__init__(self)
        self.id = id
    def _run(self):
        return self.id
    @classmethod
    def _check_completed(cls, jobid, catch_exceptions=True):
        return True
Job.register_runner_class(DoNothingRunner)

basic_config = """
[general]
admin_email: testadmin@salilab.org
service_name: test_service
state_file: state_file
socket: test.socket
check_minutes: 10

[database]
db: testdb
frontend_config: frontend.conf
backend_config: backend.conf

[directories]
install: /
incoming: %s
preprocessing: %s
failed: %s

[oldjobs]
archive: %s
expire: %s
"""

class MyJob(Job):
    def preprocess(self):
        if self.name == 'fail-preprocess':
            raise ValueError('Failure in preprocessing')
        if self.name == 'fatal-fail-preprocess':
            # Ensure that Job._fail() fails while trying to process the error
            self._metadata = None
            raise ValueError('Fatal failure in preprocessing')
        self._metadata['testfield'] = 'preprocess'
        f = open('preproc', 'w')
        f.close()
        if self.name == 'complete-preprocess':
            self.skip_run()
    def postprocess(self):
        if self.name == 'fail-postprocess':
            raise ValueError('Failure in postprocessing')
        self._metadata['testfield'] = 'postprocess'
        f = open('postproc', 'w')
        f.close()
        if self.name == 'reschedule':
            self.reschedule_run('my-reschedule')
    def complete(self):
        if self.name == 'fail-complete':
            raise ValueError('Failure in completion')
        self._metadata['testfield'] = 'complete'
        f = open('complete', 'w')
        f.close()
    def run(self):
        if self.name == 'fail-run':
            raise ValueError('Failure in running')
        self._metadata['testfield'] = 'run'
        f = open('job-output', 'w')
        f.close()
        return DoNothingRunner('MyJob ID')
    def rerun(self, data):
        f = open(data, 'w')
        f.close()
        return Job.rerun(self, data)
    def archive(self):
        if self.name == 'fail-archive':
            raise ValueError('Failure in archival')
        self._metadata['testfield'] = 'archive'
        f = open('archive', 'w')
        f.close()
    def expire(self):
        if self.name == 'fail-expire':
            raise ValueError('Failure in expiry')
        self._metadata['testfield'] = 'expire'
        f = open('expire', 'w')
        f.close()
    def _runner_done(self):
        if self.name == 'fail-batch-exception':
            raise ValueError('Failure in batch completion')
        elif self.name == 'batch-complete-race':
            # Simulate job completing just after the first check of the
            # state file
            f = open(os.path.join(self.directory, 'job-state'), 'w')
            print >> f, "DONE"
            return True
        f = open(os.path.join(self.directory, 'batch_complete'), 'w')
        f.close()
        if self.name == 'fail-batch-complete':
            return True

def add_incoming_job(db, name):
    c = db.conn.cursor()
    jobdir = os.path.join(db.config.directories['INCOMING'], name)
    os.mkdir(jobdir)
    utcnow = datetime.datetime.utcnow()
    c.execute("INSERT INTO jobs(name,state,submit_time,directory,url) " \
              + "VALUES(?,?,?,?,?)", (name, 'INCOMING', utcnow, jobdir,
                                      'http://testurl'))
    db.conn.commit()
    return jobdir

def add_running_job(db, name, completed):
    c = db.conn.cursor()
    jobdir = os.path.join(db.config.directories['RUNNING'], name)
    os.mkdir(jobdir)
    utcnow = datetime.datetime.utcnow()
    c.execute("INSERT INTO jobs(name,state,submit_time,runner_id,directory, " \
              + "contact_email,url) VALUES(?,?,?,?,?,?,?)",
              (name, 'RUNNING', utcnow, 'donothing:SGE-'+name, jobdir,
              'testuser@salilab.org', 'http://testurl'))
    db.conn.commit()
    f = open(os.path.join(jobdir, 'job-state'), 'w')
    if completed:
        print >> f, "DONE"
    else:
        print >> f, "STARTED"
    return jobdir

def add_completed_job(db, name, archive_time):
    c = db.conn.cursor()
    jobdir = os.path.join(db.config.directories['COMPLETED'], name)
    os.mkdir(jobdir)
    utcnow = datetime.datetime.utcnow()
    if archive_time is None:
        archive = None
    else:
        archive = utcnow + archive_time
    c.execute("INSERT INTO jobs(name,state,submit_time,directory, " \
              + "archive_time,url) VALUES(?,?,?,?,?,?)",
              (name, 'COMPLETED', utcnow, jobdir, archive,
               'http://testurl'))
    db.conn.commit()
    return jobdir

def add_archived_job(db, name, expire_time):
    c = db.conn.cursor()
    jobdir = os.path.join(db.config.directories['ARCHIVED'], name)
    os.mkdir(jobdir)
    utcnow = datetime.datetime.utcnow()
    if expire_time is None:
        expire = None
    else:
        expire = utcnow + expire_time
    c.execute("INSERT INTO jobs(name,state,submit_time,directory, " \
              + "expire_time,url) VALUES(?,?,?,?,?,?)",
              (name, 'ARCHIVED', utcnow, jobdir, expire,
               'http://testurl'))
    db.conn.commit()
    return jobdir

def add_failed_job(db, name):
    c = db.conn.cursor()
    jobdir = os.path.join(db.config.directories['FAILED'], name)
    os.mkdir(jobdir)
    utcnow = datetime.datetime.utcnow()
    c.execute("INSERT INTO jobs(name,state,submit_time,directory,url) " \
              + "VALUES(?,?,?,?,?)", (name, 'FAILED', utcnow, jobdir,
                                      'http://testurl'))
    db.conn.commit()
    return jobdir

def add_preprocessing_job(db, name):
    c = db.conn.cursor()
    jobdir = os.path.join(db.config.directories['PREPROCESSING'], name)
    os.mkdir(jobdir)
    utcnow = datetime.datetime.utcnow()
    c.execute("INSERT INTO jobs(name,state,submit_time,directory,url) " \
              + "VALUES(?,?,?,?,?)", (name, 'PREPROCESSING', utcnow, jobdir,
                                      'http://testurl'))
    db.conn.commit()
    return jobdir

def add_postprocessing_job(db, name):
    c = db.conn.cursor()
    jobdir = os.path.join(db.config.directories['POSTPROCESSING'], name)
    os.mkdir(jobdir)
    utcnow = datetime.datetime.utcnow()
    c.execute("INSERT INTO jobs(name,state,submit_time,directory,url) " \
              + "VALUES(?,?,?,?,?)", (name, 'POSTPROCESSING', utcnow, jobdir,
                                      'http://testurl'))
    db.conn.commit()
    return jobdir

def setup_webservice(archive='30d', expire='90d'):
    tmpdir = tempfile.mkdtemp()
    incoming = os.path.join(tmpdir, 'incoming')
    preprocessing = os.path.join(tmpdir, 'preprocessing')
    failed = os.path.join(tmpdir, 'failed')
    os.mkdir(incoming)
    os.mkdir(preprocessing)
    os.mkdir(failed)
    db = MemoryDatabase(MyJob)
    db.add_field(MySQLField('testfield', 'TEXT'))
    conf = Config(StringIO(basic_config \
                           % (incoming, preprocessing, failed, archive,
                              expire)))
    web = WebService(conf, db)
    db._create_tables()
    return db, conf, web, tmpdir

def cleanup_webservice(conf, tmpdir):
    os.rmdir(conf.directories['PREPROCESSING'])
    os.rmdir(conf.directories['INCOMING'])
    os.rmdir(conf.directories['FAILED'])
    os.rmdir(tmpdir)

class JobTest(unittest.TestCase):
    """Check Job class"""

    def assert_fail_msg(self, failre, job):
        self.assert_(re.search(failre, job._metadata['failure'],
                               flags=re.DOTALL),
                     'Unexpected failure message: ' + job._metadata['failure'])

    def test_ok_startup(self):
        """Check successful startup of incoming jobs"""
        db, conf, web, tmpdir = setup_webservice()
        injobdir = add_incoming_job(db, 'job1')
        web._process_incoming_jobs()

        # Job should now have moved from INCOMING to RUNNING
        job = web.get_job_by_name('RUNNING', 'job1')
        runjobdir = os.path.join(conf.directories['RUNNING'], 'job1')
        self.assertEqual(job.directory, runjobdir)
        # New fields should have been populated in the database
        self.assertEqual(job._metadata['testfield'], 'run')
        self.assertEqual(job._metadata['runner_id'], 'donothing:MyJob ID')
        self.assertNotEqual(job._metadata['preprocess_time'], None)
        self.assertNotEqual(job._metadata['run_time'], None)
        # Both preprocess and run methods in MyJob should have triggered
        os.unlink(os.path.join(runjobdir, 'preproc'))
        os.unlink(os.path.join(runjobdir, 'job-output'))
        os.rmdir(runjobdir)
        cleanup_webservice(conf, tmpdir)

    def test_sanity_check_no_directory(self):
        """Make sure that sanity checks catch jobs without directories"""
        utcnow = datetime.datetime.utcnow()
        db, conf, web, tmpdir = setup_webservice()
        c = db.conn.cursor()
        c.execute("INSERT INTO jobs(name,state,submit_time,directory,url) " \
                  + "VALUES(?,?,?,?,?)", ('job1', 'INCOMING', utcnow, None,
                                          'http://testurl'))
        db.conn.commit()
        web._process_incoming_jobs()
        job = web.get_job_by_name('FAILED', 'job1')
        self.assertEqual(job.directory, None)
        self.assert_fail_msg('Python exception:.*Traceback.*' \
                             + 'SanityError: .*did not set the directory', job)
        cleanup_webservice(conf, tmpdir)

    def test_sanity_check_invalid_directory(self):
        """Make sure that sanity checks catch invalid job directories"""
        utcnow = datetime.datetime.utcnow()
        db, conf, web, tmpdir = setup_webservice()
        c = db.conn.cursor()
        c.execute("INSERT INTO jobs(name,state,submit_time,directory,url) " \
                  + "VALUES(?,?,?,?,?)", ('job2', 'INCOMING', utcnow,
                                          '/not/exist', 'http://testurl'))
        db.conn.commit()
        web._process_incoming_jobs()
        job = web.get_job_by_name('FAILED', 'job2')
        self.assertEqual(job.directory, None)
        self.assert_fail_msg('Python exception:.*Traceback.*' \
                             + 'SanityError: .*is not a directory', job)
        cleanup_webservice(conf, tmpdir)

    def test_sanity_check_preproc_state(self):
        """Make sure that sanity checks catch jobs in PREPROCESSING state"""
        utcnow = datetime.datetime.utcnow()
        db, conf, web, tmpdir = setup_webservice()
        jobdir = add_preprocessing_job(db, 'preproc')
        web._sanity_check()
        job = web.get_job_by_name('FAILED', 'preproc')
        failjobdir = os.path.join(conf.directories['FAILED'], 'preproc')
        self.assertEqual(job.directory, failjobdir)
        os.rmdir(failjobdir)
        self.assert_fail_msg('Python exception:.*Traceback.*' \
                             + 'SanityError: .*is in state PREPROCESSING', job)
        cleanup_webservice(conf, tmpdir)

    def test_sanity_check_postproc_state(self):
        """Make sure that sanity checks catch jobs in POSTPROCESSING state"""
        utcnow = datetime.datetime.utcnow()
        db, conf, web, tmpdir = setup_webservice()
        jobdir = add_postprocessing_job(db, 'postproc')
        web._sanity_check()
        job = web.get_job_by_name('FAILED', 'postproc')
        failjobdir = os.path.join(conf.directories['FAILED'], 'postproc')
        self.assertEqual(job.directory, failjobdir)
        os.rmdir(failjobdir)
        self.assert_fail_msg('Python exception:.*Traceback.*' \
                             + 'SanityError: .*is in state POSTPROCESSING', job)
        cleanup_webservice(conf, tmpdir)

    def test_preprocess_failure(self):
        """Make sure that preprocess failures are handled correctly"""
        db, conf, web, tmpdir = setup_webservice()
        injobdir = add_incoming_job(db, 'fail-preprocess')
        web._process_incoming_jobs()

        # Job should now have moved from INCOMING to FAILED
        job = web.get_job_by_name('FAILED', 'fail-preprocess')
        failjobdir = os.path.join(conf.directories['FAILED'], 'fail-preprocess')
        self.assertEqual(job.directory, failjobdir)
        self.assertEqual(job._metadata['runner_id'], None)
        self.assert_fail_msg('Python exception:.*Traceback.*' \
                             + 'ValueError: Failure in preprocessing', job)
        os.rmdir(failjobdir)
        cleanup_webservice(conf, tmpdir)
        # Make sure that the admin got a failed job email
        mail = conf.get_mail_output()
        self.assert_(re.search('Subject: .*From: testadmin.*To: testadmin' \
                               + '.*Failure in preprocessing', mail,
                               flags=re.DOTALL),
                     'Unexpected mail output: ' + mail)

    def test_fatal_failure(self):
        """Make sure that job failures within _fail() are handled correctly"""
        db, conf, web, tmpdir = setup_webservice()
        injobdir = add_incoming_job(db, 'fatal-fail-preprocess')
        # Fatal error should be propagated
        self.assertRaises(TypeError, web._process_incoming_jobs)
        # Job should be stuck in PREPROCESSING
        jobdir = os.path.join(conf.directories['PREPROCESSING'],
                              'fatal-fail-preprocess')
        os.rmdir(jobdir)
        cleanup_webservice(conf, tmpdir)
        # Make sure that state_file and email contain both the fatal error
        # and the original job error that triggered _fail():
        expect = 'Traceback.*TypeError: .*object.*' + \
                 'This error in turn occurred while trying to handle ' + \
                 'the original error below:.*Traceback.*' + \
                 'ValueError: Fatal failure in preprocessing'
        state = open('state_file').read()
        self.assert_(re.search(expect, state, flags=re.DOTALL),
                     'Unexpected state file ' + state)
        os.unlink('state_file')
        mail = conf.get_mail_output()
        self.assert_(re.search(expect, state, flags=re.DOTALL),
                     'Unexpected mail output: ' + mail)

    def test_preprocess_complete(self):
        """Job.preprocess() should be able to skip a job run"""
        db, conf, web, tmpdir = setup_webservice()
        injobdir = add_incoming_job(db, 'complete-preprocess')
        web._process_incoming_jobs()

        # Job should now have moved directly from INCOMING to COMPLETED
        job = web.get_job_by_name('COMPLETED', 'complete-preprocess')
        compjobdir = os.path.join(conf.directories['COMPLETED'],
                                  'complete-preprocess')
        self.assertEqual(job.directory, compjobdir)
        # Just the preprocess and complete methods in MyJob should have
        # triggered; no info from run should be present
        os.unlink(os.path.join(compjobdir, 'preproc'))
        os.unlink(os.path.join(compjobdir, 'complete'))
        self.assertEqual(job._metadata['testfield'], 'complete')
        self.assertEqual(job._metadata['runner_id'], None)
        self.assertEqual(job._metadata['run_time'], None)
        self.assertEqual(job._metadata['postprocess_time'], None)
        os.rmdir(compjobdir)
        cleanup_webservice(conf, tmpdir)

    def test_run_failure(self):
        """Make sure that run failures are handled correctly"""
        db, conf, web, tmpdir = setup_webservice()
        injobdir = add_incoming_job(db, 'fail-run')
        web._process_incoming_jobs()

        # Job should now have moved from INCOMING to FAILED
        job = web.get_job_by_name('FAILED', 'fail-run')
        failjobdir = os.path.join(conf.directories['FAILED'], 'fail-run')
        self.assertEqual(job.directory, failjobdir)
        self.assertEqual(job._metadata['testfield'], 'preprocess')
        self.assertEqual(job._metadata['runner_id'], None)
        self.assert_fail_msg('Python exception:.*Traceback.*' \
                             + 'ValueError: Failure in running', job)
        # Just the preprocess method in MyJob should have triggered
        os.unlink(os.path.join(failjobdir, 'preproc'))
        os.rmdir(failjobdir)
        cleanup_webservice(conf, tmpdir)

    def test_ok_complete(self):
        """Check normal job completion"""
        db, conf, web, tmpdir = setup_webservice()
        runjobdir = add_running_job(db, 'job1', completed=True)
        web._process_completed_jobs()

        # Job should now have moved from RUNNING to COMPLETED
        job = web.get_job_by_name('COMPLETED', 'job1')
        compjobdir = os.path.join(conf.directories['COMPLETED'], 'job1')
        self.assertEqual(job.directory, compjobdir)
        # New fields should have been populated in the database
        self.assertEqual(job._metadata['testfield'], 'complete')
        self.assertNotEqual(job._metadata['postprocess_time'], None)
        self.assertNotEqual(job._metadata['end_time'], None)
        self.assertNotEqual(job._metadata['archive_time'], None)
        self.assertNotEqual(job._metadata['expire_time'], None)
        # postprocess and complete methods in MyJob should have triggered
        os.unlink(os.path.join(compjobdir, 'postproc'))
        os.unlink(os.path.join(compjobdir, 'complete'))
        # Should have checked for batch completion
        os.unlink(os.path.join(compjobdir, 'batch_complete'))
        os.rmdir(compjobdir)
        cleanup_webservice(conf, tmpdir)
        # User should have been notified by email
        mail = conf.get_mail_output()
        self.assert_(re.search('Subject: .*From: testadmin.*To: testuser' \
                               + '.*Your job job1 has finished.*http://testurl',
                               mail, flags=re.DOTALL),
                     'Unexpected mail output: ' + mail)

    def test_complete_no_expire(self):
        """Check completion of a job that should never expire or be archived"""
        db, conf, web, tmpdir = setup_webservice(expire='NEVER',
                                                 archive='NEVER')
        runjobdir = add_running_job(db, 'job1', completed=True)
        web._process_completed_jobs()

        # Job should now have moved from RUNNING to COMPLETED
        job = web.get_job_by_name('COMPLETED', 'job1')
        jobdir = os.path.join(conf.directories['COMPLETED'], 'job1')
        self.assertEqual(job.directory, jobdir)
        # archive/expire times should still be NULL
        self.assertEqual(job._metadata['archive_time'], None)
        self.assertEqual(job._metadata['expire_time'], None)
        os.unlink(os.path.join(jobdir, 'postproc'))
        os.unlink(os.path.join(jobdir, 'complete'))
        os.unlink(os.path.join(jobdir, 'batch_complete'))
        os.rmdir(jobdir)
        cleanup_webservice(conf, tmpdir)

    def test_still_running(self):
        """Check that jobs that are still running are not processed"""
        db, conf, web, tmpdir = setup_webservice()
        runjobdir = add_running_job(db, 'job1', completed=False)
        web._process_completed_jobs()

        # Job should still be in RUNNING state
        job = web.get_job_by_name('RUNNING', 'job1')
        runjobdir = os.path.join(conf.directories['RUNNING'], 'job1')
        self.assertEqual(job.directory, runjobdir)
        os.unlink(os.path.join(runjobdir, 'job-state'))
        # Should have checked for batch completion
        os.unlink(os.path.join(runjobdir, 'batch_complete'))
        os.rmdir(runjobdir)
        cleanup_webservice(conf, tmpdir)

    def test_postprocess_failure(self):
        """Make sure that postprocess failures are handled correctly"""
        db, conf, web, tmpdir = setup_webservice()
        runjobdir = add_running_job(db, 'fail-postprocess', completed=True)
        web._process_completed_jobs()

        # Job should now have moved from RUNNING to FAILED
        job = web.get_job_by_name('FAILED', 'fail-postprocess')
        failjobdir = os.path.join(conf.directories['FAILED'],
                                  'fail-postprocess')
        self.assertEqual(job.directory, failjobdir)
        self.assert_fail_msg('Python exception:.*Traceback.*' \
                             + 'ValueError: Failure in postprocessing', job)
        os.unlink(os.path.join(failjobdir, 'batch_complete'))
        os.rmdir(failjobdir)
        cleanup_webservice(conf, tmpdir)

    def test_complete_failure(self):
        """Make sure that complete failures are handled correctly"""
        db, conf, web, tmpdir = setup_webservice()
        runjobdir = add_running_job(db, 'fail-complete', completed=True)
        web._process_completed_jobs()

        # Job should now have moved from RUNNING to FAILED
        job = web.get_job_by_name('FAILED', 'fail-complete')
        failjobdir = os.path.join(conf.directories['FAILED'],
                                  'fail-complete')
        self.assertEqual(job.directory, failjobdir)
        self.assert_fail_msg('Python exception:.*Traceback.*' \
                             + 'ValueError: Failure in completion', job)
        # postprocess method in MyJob should have triggered
        os.unlink(os.path.join(failjobdir, 'postproc'))
        # should have checked for batch completion
        os.unlink(os.path.join(failjobdir, 'batch_complete'))
        os.rmdir(failjobdir)
        cleanup_webservice(conf, tmpdir)

    def test_batch_failure(self):
        """Make sure that batch system failures are handled correctly"""
        db, conf, web, tmpdir = setup_webservice()
        runjobdir = add_running_job(db, 'fail-batch-complete', completed=False)
        web._process_completed_jobs()

        # Job should now have moved from RUNNING to FAILED
        job = web.get_job_by_name('FAILED', 'fail-batch-complete')
        failjobdir = os.path.join(conf.directories['FAILED'],
                                  'fail-batch-complete')
        self.assertEqual(job.directory, failjobdir)
        self.assert_fail_msg('Python exception:.*Traceback.*'
                             'RunnerError: Runner claims job '
                             'donothing:SGE-fail-batch-complete is complete, '
                             'but job-state file in job directory', job)
        os.unlink(os.path.join(failjobdir, 'job-state'))
        # Should have checked for batch completion
        os.unlink(os.path.join(failjobdir, 'batch_complete'))
        os.rmdir(failjobdir)
        cleanup_webservice(conf, tmpdir)

    def test_batch_exception(self):
        """Make sure that exceptions in check_completed are handled"""
        db, conf, web, tmpdir = setup_webservice()
        runjobdir = add_running_job(db, 'fail-batch-exception', completed=False)
        web._process_completed_jobs()

        # Job should now have moved from RUNNING to FAILED
        job = web.get_job_by_name('FAILED', 'fail-batch-exception')
        failjobdir = os.path.join(conf.directories['FAILED'],
                                  'fail-batch-exception')
        self.assertEqual(job.directory, failjobdir)
        self.assert_fail_msg('Python exception:.*Traceback.*' \
                             + 'ValueError: Failure in batch completion', job)
        os.unlink(os.path.join(failjobdir, 'job-state'))
        os.rmdir(failjobdir)
        cleanup_webservice(conf, tmpdir)

    def test_ok_archive(self):
        """Check successful archival of completed jobs"""
        db, conf, web, tmpdir = setup_webservice()
        injobdir = add_completed_job(db, 'job1', datetime.timedelta(days=-1))
        web._process_old_jobs()

        # Job should now have moved from COMPLETED to ARCHIVED
        job = web.get_job_by_name('ARCHIVED', 'job1')
        arcjobdir = os.path.join(conf.directories['ARCHIVED'], 'job1')
        self.assertEqual(job.directory, arcjobdir)
        self.assertEqual(job._metadata['testfield'], 'archive')
        # archive method in MyJob should have triggered
        os.unlink(os.path.join(arcjobdir, 'archive'))
        os.rmdir(arcjobdir)
        cleanup_webservice(conf, tmpdir)

    def test_archive_failure(self):
        """Make sure that archival failures are handled correctly"""
        db, conf, web, tmpdir = setup_webservice()
        injobdir = add_completed_job(db, 'fail-archive',
                                     datetime.timedelta(days=-1))
        web._process_old_jobs()

        # Job should now have moved from COMPLETED to FAILED
        job = web.get_job_by_name('FAILED', 'fail-archive')
        failjobdir = os.path.join(conf.directories['FAILED'],
                                  'fail-archive')
        self.assertEqual(job.directory, failjobdir)
        self.assert_fail_msg('Python exception:.*Traceback.*' \
                             + 'ValueError: Failure in archival', job)
        os.rmdir(failjobdir)
        cleanup_webservice(conf, tmpdir)

    def test_never_archive(self):
        """Check for jobs that never archive"""
        db, conf, web, tmpdir = setup_webservice()
        injobdir = add_completed_job(db, 'job1', None)
        web._process_old_jobs()

        # Job should still be COMPLETED
        job = web.get_job_by_name('COMPLETED', 'job1')
        jobdir = os.path.join(conf.directories['COMPLETED'], 'job1')
        self.assertEqual(job.directory, jobdir)
        os.rmdir(jobdir)
        cleanup_webservice(conf, tmpdir)

    def test_ok_expire(self):
        """Check successful expiry of archived jobs"""
        db, conf, web, tmpdir = setup_webservice()
        injobdir = add_archived_job(db, 'job1', datetime.timedelta(days=-1))
        web._process_old_jobs()

        # Job should now have moved from ARCHIVED to EXPIRED
        job = web.get_job_by_name('EXPIRED', 'job1')
        self.assertEqual(job.directory, None)
        self.assertEqual(job._metadata['testfield'], 'expire')
        # expire method in MyJob should have triggered
        os.unlink('expire')
        cleanup_webservice(conf, tmpdir)

    def test_never_expire(self):
        """Check for jobs that never expire"""
        db, conf, web, tmpdir = setup_webservice()
        injobdir = add_archived_job(db, 'job1', None)
        web._process_old_jobs()

        # Job should still be ARCHIVED
        job = web.get_job_by_name('ARCHIVED', 'job1')
        arcjobdir = os.path.join(conf.directories['ARCHIVED'], 'job1')
        self.assertEqual(job.directory, arcjobdir)
        os.rmdir(arcjobdir)
        cleanup_webservice(conf, tmpdir)

    def test_expire_failure(self):
        """Make sure that expiry failures are handled correctly"""
        db, conf, web, tmpdir = setup_webservice()
        injobdir = add_archived_job(db, 'fail-expire',
                                    datetime.timedelta(days=-1))
        web._process_old_jobs()

        # Job should now have moved from ARCHIVED to FAILED
        job = web.get_job_by_name('FAILED', 'fail-expire')
        # Job directory should be None since EXPIRED state was visited
        self.assertEqual(job.directory, None)
        self.assert_fail_msg('Python exception:.*Traceback.*' \
                             + 'ValueError: Failure in expiry', job)
        cleanup_webservice(conf, tmpdir)

    def test_ok_resubmit(self):
        """Check successful resubmission of failed jobs"""
        db, conf, web, tmpdir = setup_webservice()
        injobdir = add_failed_job(db, 'job1')
        job = web.get_job_by_name('FAILED', 'job1')
        job.resubmit()

        # Job should now have moved from FAILED to INCOMING
        job = web.get_job_by_name('INCOMING', 'job1')
        # Can only resubmit FAILED jobs
        self.assertRaises(InvalidStateError, job.resubmit)
        injobdir = os.path.join(conf.directories['INCOMING'], 'job1')
        self.assertEqual(job.directory, injobdir)
        os.rmdir(injobdir)
        cleanup_webservice(conf, tmpdir)

    def test_has_completed(self):
        """Check Job._has_completed method"""
        db, conf, web, tmpdir = setup_webservice()
        runjobdir = add_running_job(db, 'batch-complete-race', completed=False)
        job = web.get_job_by_name('RUNNING', 'batch-complete-race')
        # In r62 and earlier, a race condition could cause a failure here if
        # the SGE job finished just after the state file check is done
        self.assertEqual(job._has_completed(), True)

    def test_skip_run(self):
        """Check Job.skip_run method"""
        db, conf, web, tmpdir = setup_webservice()
        runjobdir = add_running_job(db, 'test', completed=False)
        job = web.get_job_by_name('RUNNING', 'test')
        # skip_run should only work on PREPROCESSING jobs
        self.assertRaises(InvalidStateError, job.skip_run)

    def test_reschedule(self):
        """Check rescheduling of jobs"""
        db, conf, web, tmpdir = setup_webservice()
        runjobdir = add_running_job(db, 'reschedule', completed=True)
        web._process_completed_jobs()

        # Job should have been rescheduled, so should have entered the
        # POSTPROCSSING state but now be RUNNING again
        job = web.get_job_by_name('RUNNING', 'reschedule')
        jobdir = os.path.join(conf.directories['RUNNING'], 'reschedule')
        self.assertEqual(job.directory, jobdir)
        # postprocess, rerun and run methods in MyJob should have triggered
        os.unlink(os.path.join(jobdir, 'postproc'))
        os.unlink(os.path.join(jobdir, 'my-reschedule'))
        os.unlink(os.path.join(jobdir, 'job-output'))
        # Should have checked for batch completion
        os.unlink(os.path.join(jobdir, 'batch_complete'))
        # Rescheduled jobs should *not* set run_time but should set
        # postprocess_time
        self.assertEqual(job._metadata['run_time'], None)
        self.assertNotEqual(job._metadata['postprocess_time'], None)
        os.rmdir(jobdir)
        cleanup_webservice(conf, tmpdir)
        # User should *not* been notified by email
        mail = conf.get_mail_output()
        self.assertEqual(mail, None)

    def test_reschedule_run(self):
        """Check Job.reschedule_run method"""
        db, conf, web, tmpdir = setup_webservice()
        runjobdir = add_running_job(db, 'test', completed=False)
        job = web.get_job_by_name('RUNNING', 'test')
        # reschedule_run should only work on POSTPROCESSING jobs
        self.assertRaises(InvalidStateError, job.reschedule_run)

if __name__ == '__main__':
    unittest.main()
