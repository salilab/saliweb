import unittest
import datetime
import os
import tempfile
from memory_database import MemoryDatabase
from saliweb.backend import WebService, Config, Job, InvalidStateError
from StringIO import StringIO

basic_config = """
[database]
user: dbuser
db: testdb
passwd: dbtest

[directories]
incoming: %s
preprocessing: %s
failed: %s

[oldjobs]
archive: 30d
expire: 90d
"""

class MyJob(Job):
    def preprocess(self):
        if self.name == 'fail-preprocess':
            raise ValueError('Failure in preprocessing')
        f = open('preproc', 'w')
        f.close()
        if self.name == 'complete-preprocess':
            return False
    def postprocess(self):
        if self.name == 'fail-postprocess':
            raise ValueError('Failure in postprocessing')
        f = open('postproc', 'w')
        f.close()
    def complete(self):
        if self.name == 'fail-complete':
            raise ValueError('Failure in completion')
        f = open('complete', 'w')
        f.close()
    def run(self):
        if self.name == 'fail-run':
            raise ValueError('Failure in running')
        f = open('job-output', 'w')
        f.close()
        return 'MyJob ID'
    def archive(self):
        if self.name == 'fail-archive':
            raise ValueError('Failure in archival')
        f = open('archive', 'w')
        f.close()
    def expire(self):
        if self.name == 'fail-expire':
            raise ValueError('Failure in expiry')
        f = open('expire', 'w')
        f.close()
    def check_batch_completed(self, jobid):
        if self.name == 'fail-batch-complete':
            return True
        elif self.name == 'fail-batch-exception':
            raise ValueError('Failure in batch completion')

def add_incoming_job(db, name):
    c = db.conn.cursor()
    jobdir = os.path.join(db.config.directories['INCOMING'], name)
    os.mkdir(jobdir)
    utcnow = datetime.datetime.utcnow()
    c.execute("INSERT INTO jobs(name,state,submit_time,directory) " \
              + "VALUES(?,?,?,?)", (name, 'INCOMING', utcnow, jobdir))
    db.conn.commit()
    return jobdir

def add_running_job(db, name, completed):
    c = db.conn.cursor()
    jobdir = os.path.join(db.config.directories['RUNNING'], name)
    os.mkdir(jobdir)
    utcnow = datetime.datetime.utcnow()
    c.execute("INSERT INTO jobs(name,state,submit_time,runjob_id,directory) " \
              + "VALUES(?,?,?,?,?)",
              (name, 'RUNNING', utcnow, 'SGE-'+name, jobdir))
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
    c.execute("INSERT INTO jobs(name,state,submit_time,directory, " \
              + "archive_time) VALUES(?,?,?,?,?)",
              (name, 'COMPLETED', utcnow, jobdir, utcnow + archive_time))
    db.conn.commit()
    return jobdir

def add_archived_job(db, name, expire_time):
    c = db.conn.cursor()
    jobdir = os.path.join(db.config.directories['ARCHIVED'], name)
    os.mkdir(jobdir)
    utcnow = datetime.datetime.utcnow()
    c.execute("INSERT INTO jobs(name,state,submit_time,directory, " \
              + "expire_time) VALUES(?,?,?,?,?)",
              (name, 'ARCHIVED', utcnow, jobdir, utcnow + expire_time))
    db.conn.commit()
    return jobdir

def add_failed_job(db, name):
    c = db.conn.cursor()
    jobdir = os.path.join(db.config.directories['FAILED'], name)
    os.mkdir(jobdir)
    utcnow = datetime.datetime.utcnow()
    c.execute("INSERT INTO jobs(name,state,submit_time,directory) " \
              + "VALUES(?,?,?,?)", (name, 'FAILED', utcnow, jobdir))
    db.conn.commit()
    return jobdir

def setup_webservice():
    tmpdir = tempfile.mkdtemp()
    incoming = os.path.join(tmpdir, 'incoming')
    preprocessing = os.path.join(tmpdir, 'preprocessing')
    failed = os.path.join(tmpdir, 'failed')
    os.mkdir(incoming)
    os.mkdir(preprocessing)
    os.mkdir(failed)
    db = MemoryDatabase(MyJob)
    conf = Config(StringIO(basic_config \
                           % (incoming, preprocessing, failed)))
    web = WebService(conf, db)
    db.create_tables()
    return db, conf, web, tmpdir

def cleanup_webservice(conf, tmpdir):
    os.rmdir(conf.directories['PREPROCESSING'])
    os.rmdir(conf.directories['INCOMING'])
    os.rmdir(conf.directories['FAILED'])
    os.rmdir(tmpdir)

class JobTest(unittest.TestCase):
    """Check Job class"""

    def test_ok_startup(self):
        """Check successful startup of incoming jobs"""
        db, conf, web, tmpdir = setup_webservice()
        injobdir = add_incoming_job(db, 'job1')
        web.process_incoming_jobs()

        # Job should now have moved from INCOMING to RUNNING
        job = web.get_job_by_name('RUNNING', 'job1')
        runjobdir = os.path.join(conf.directories['RUNNING'], 'job1')
        self.assertEqual(job.directory, runjobdir)
        # New fields should have been populated in the database
        self.assertEqual(job._jobdict['runjob_id'], 'MyJob ID')
        self.assertNotEqual(job._jobdict['preprocess_time'], None)
        self.assertNotEqual(job._jobdict['run_time'], None)
        # Both preprocess and run methods in MyJob should have triggered
        os.unlink(os.path.join(runjobdir, 'preproc'))
        os.unlink(os.path.join(runjobdir, 'job-output'))
        os.rmdir(runjobdir)
        cleanup_webservice(conf, tmpdir)

    def test_preprocess_failure(self):
        """Make sure that preprocess failures are handled correctly"""
        db, conf, web, tmpdir = setup_webservice()
        injobdir = add_incoming_job(db, 'fail-preprocess')
        web.process_incoming_jobs()

        # Job should now have moved from INCOMING to FAILED
        job = web.get_job_by_name('FAILED', 'fail-preprocess')
        failjobdir = os.path.join(conf.directories['FAILED'], 'fail-preprocess')
        self.assertEqual(job.directory, failjobdir)
        self.assertEqual(job._jobdict['runjob_id'], None)
        self.assertEqual(job._jobdict['failure'],
                         'Python exception: Failure in preprocessing')
        os.rmdir(failjobdir)
        cleanup_webservice(conf, tmpdir)

    def test_preprocess_complete(self):
        """Job.preprocess() should be able to skip a job run"""
        db, conf, web, tmpdir = setup_webservice()
        injobdir = add_incoming_job(db, 'complete-preprocess')
        web.process_incoming_jobs()

        # Job should now have moved directly from INCOMING to COMPLETED
        job = web.get_job_by_name('COMPLETED', 'complete-preprocess')
        compjobdir = os.path.join(conf.directories['COMPLETED'],
                                  'complete-preprocess')
        self.assertEqual(job.directory, compjobdir)
        # Just the preprocess and complete methods in MyJob should have
        # triggered; no info from run should be present
        os.unlink(os.path.join(compjobdir, 'preproc'))
        os.unlink(os.path.join(compjobdir, 'complete'))
        self.assertEqual(job._jobdict['runjob_id'], None)
        self.assertEqual(job._jobdict['run_time'], None)
        self.assertEqual(job._jobdict['postprocess_time'], None)
        os.rmdir(compjobdir)
        cleanup_webservice(conf, tmpdir)

    def test_run_failure(self):
        """Make sure that run failures are handled correctly"""
        db, conf, web, tmpdir = setup_webservice()
        injobdir = add_incoming_job(db, 'fail-run')
        web.process_incoming_jobs()

        # Job should now have moved from INCOMING to FAILED
        job = web.get_job_by_name('FAILED', 'fail-run')
        failjobdir = os.path.join(conf.directories['FAILED'], 'fail-run')
        self.assertEqual(job.directory, failjobdir)
        self.assertEqual(job._jobdict['runjob_id'], None)
        self.assertEqual(job._jobdict['failure'],
                         'Python exception: Failure in running')
        # Just the preprocess method in MyJob should have triggered
        os.unlink(os.path.join(failjobdir, 'preproc'))
        os.rmdir(failjobdir)
        cleanup_webservice(conf, tmpdir)

    def test_ok_complete(self):
        """Check normal job completion"""
        db, conf, web, tmpdir = setup_webservice()
        runjobdir = add_running_job(db, 'job1', completed=True)
        web.process_completed_jobs()

        # Job should now have moved from RUNNING to COMPLETED
        job = web.get_job_by_name('COMPLETED', 'job1')
        compjobdir = os.path.join(conf.directories['COMPLETED'], 'job1')
        self.assertEqual(job.directory, compjobdir)
        # New fields should have been populated in the database
        self.assertNotEqual(job._jobdict['postprocess_time'], None)
        self.assertNotEqual(job._jobdict['end_time'], None)
        self.assertNotEqual(job._jobdict['archive_time'], None)
        self.assertNotEqual(job._jobdict['expire_time'], None)
        # postprocess and complete methods in MyJob should have triggered
        os.unlink(os.path.join(compjobdir, 'postproc'))
        os.unlink(os.path.join(compjobdir, 'complete'))
        os.rmdir(compjobdir)
        cleanup_webservice(conf, tmpdir)

    def test_still_running(self):
        """Check that jobs that are still running are not processed"""
        db, conf, web, tmpdir = setup_webservice()
        runjobdir = add_running_job(db, 'job1', completed=False)
        web.process_completed_jobs()

        # Job should still be in RUNNING state
        job = web.get_job_by_name('RUNNING', 'job1')
        runjobdir = os.path.join(conf.directories['RUNNING'], 'job1')
        self.assertEqual(job.directory, runjobdir)
        os.unlink(os.path.join(runjobdir, 'job-state'))
        os.rmdir(runjobdir)
        cleanup_webservice(conf, tmpdir)

    def test_postprocess_failure(self):
        """Make sure that postprocess failures are handled correctly"""
        db, conf, web, tmpdir = setup_webservice()
        runjobdir = add_running_job(db, 'fail-postprocess', completed=True)
        web.process_completed_jobs()

        # Job should now have moved from RUNNING to FAILED
        job = web.get_job_by_name('FAILED', 'fail-postprocess')
        failjobdir = os.path.join(conf.directories['FAILED'],
                                  'fail-postprocess')
        self.assertEqual(job.directory, failjobdir)
        self.assertEqual(job._jobdict['failure'],
                         'Python exception: Failure in postprocessing')
        os.rmdir(failjobdir)
        cleanup_webservice(conf, tmpdir)

    def test_complete_failure(self):
        """Make sure that complete failures are handled correctly"""
        db, conf, web, tmpdir = setup_webservice()
        runjobdir = add_running_job(db, 'fail-complete', completed=True)
        web.process_completed_jobs()

        # Job should now have moved from RUNNING to FAILED
        job = web.get_job_by_name('FAILED', 'fail-complete')
        failjobdir = os.path.join(conf.directories['FAILED'],
                                  'fail-complete')
        self.assertEqual(job.directory, failjobdir)
        self.assertEqual(job._jobdict['failure'],
                         'Python exception: Failure in completion')
        # postprocess method in MyJob should have triggered
        os.unlink(os.path.join(failjobdir, 'postproc'))
        os.rmdir(failjobdir)
        cleanup_webservice(conf, tmpdir)

    def test_batch_failure(self):
        """Make sure that batch system failures are handled correctly"""
        db, conf, web, tmpdir = setup_webservice()
        runjobdir = add_running_job(db, 'fail-batch-complete', completed=False)
        web.process_completed_jobs()

        # Job should now have moved from RUNNING to FAILED
        job = web.get_job_by_name('FAILED', 'fail-batch-complete')
        failjobdir = os.path.join(conf.directories['FAILED'],
                                  'fail-batch-complete')
        self.assertEqual(job.directory, failjobdir)
        self.assert_(job._jobdict['failure'].startswith( \
                      'Python exception: Batch system claims job ' \
                      + 'SGE-fail-batch-complete is complete'))
        os.unlink(os.path.join(failjobdir, 'job-state'))
        os.rmdir(failjobdir)
        cleanup_webservice(conf, tmpdir)

    def test_batch_exception(self):
        """Make sure that exceptions in check_batch_completed are handled"""
        db, conf, web, tmpdir = setup_webservice()
        runjobdir = add_running_job(db, 'fail-batch-exception', completed=False)
        web.process_completed_jobs()

        # Job should now have moved from RUNNING to FAILED
        job = web.get_job_by_name('FAILED', 'fail-batch-exception')
        failjobdir = os.path.join(conf.directories['FAILED'],
                                  'fail-batch-exception')
        self.assertEqual(job.directory, failjobdir)
        self.assertEqual(job._jobdict['failure'],
                         'Python exception: Failure in batch completion')
        os.unlink(os.path.join(failjobdir, 'job-state'))
        os.rmdir(failjobdir)
        cleanup_webservice(conf, tmpdir)

    def test_ok_archive(self):
        """Check successful archival of completed jobs"""
        db, conf, web, tmpdir = setup_webservice()
        injobdir = add_completed_job(db, 'job1', datetime.timedelta(days=-1))
        web.process_old_jobs()

        # Job should now have moved from COMPLETED to ARCHIVED
        job = web.get_job_by_name('ARCHIVED', 'job1')
        arcjobdir = os.path.join(conf.directories['ARCHIVED'], 'job1')
        self.assertEqual(job.directory, arcjobdir)
        # archive method in MyJob should have triggered
        os.unlink(os.path.join(arcjobdir, 'archive'))
        os.rmdir(arcjobdir)
        cleanup_webservice(conf, tmpdir)

    def test_archive_failure(self):
        """Make sure that archival failures are handled correctly"""
        db, conf, web, tmpdir = setup_webservice()
        injobdir = add_completed_job(db, 'fail-archive',
                                     datetime.timedelta(days=-1))
        web.process_old_jobs()

        # Job should now have moved from COMPLETED to FAILED
        job = web.get_job_by_name('FAILED', 'fail-archive')
        failjobdir = os.path.join(conf.directories['FAILED'],
                                  'fail-archive')
        self.assertEqual(job.directory, failjobdir)
        self.assertEqual(job._jobdict['failure'],
                         'Python exception: Failure in archival')
        os.rmdir(failjobdir)
        cleanup_webservice(conf, tmpdir)

    def test_ok_expire(self):
        """Check successful expiry of archived jobs"""
        db, conf, web, tmpdir = setup_webservice()
        injobdir = add_archived_job(db, 'job1', datetime.timedelta(days=-1))
        web.process_old_jobs()

        # Job should now have moved from ARCHIVED to EXPIRED
        job = web.get_job_by_name('EXPIRED', 'job1')
        expjobdir = os.path.join(conf.directories['EXPIRED'], 'job1')
        self.assertEqual(job.directory, expjobdir)
        # expire method in MyJob should have triggered
        os.unlink(os.path.join(expjobdir, 'expire'))
        os.rmdir(expjobdir)
        cleanup_webservice(conf, tmpdir)

    def test_expire_failure(self):
        """Make sure that expiry failures are handled correctly"""
        db, conf, web, tmpdir = setup_webservice()
        injobdir = add_archived_job(db, 'fail-expire',
                                    datetime.timedelta(days=-1))
        web.process_old_jobs()

        # Job should now have moved from ARCHIVED to FAILED
        job = web.get_job_by_name('FAILED', 'fail-expire')
        failjobdir = os.path.join(conf.directories['FAILED'],
                                  'fail-expire')
        self.assertEqual(job.directory, failjobdir)
        self.assertEqual(job._jobdict['failure'],
                         'Python exception: Failure in expiry')
        os.rmdir(failjobdir)
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

if __name__ == '__main__':
    unittest.main()
