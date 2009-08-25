import unittest
import datetime
import os
import tempfile
from memory_database import MemoryDatabase
from saliweb.backend import WebService, Config, Job
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
        f = open('preproc', 'w')
        f.close()
    def run(self):
        f = open('job-output', 'w')
        f.close()

def add_incoming_job(db, name):
    c = db.conn.cursor()
    jobdir = os.path.join(db.config.directories['INCOMING'], name)
    os.mkdir(jobdir)
    utcnow = datetime.datetime.utcnow()
    c.execute("INSERT INTO INCOMING(name,submit_time,directory) VALUES(?,?,?)",
              (name, utcnow, jobdir))
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
        # Both preprocess and run methods in MyJob should have triggered
        os.unlink(os.path.join(runjobdir, 'preproc'))
        os.unlink(os.path.join(runjobdir, 'job-output'))
        os.rmdir(runjobdir)
        cleanup_webservice(conf, tmpdir)

if __name__ == '__main__':
    unittest.main()
