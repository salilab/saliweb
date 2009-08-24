import unittest
import sqlite3
import time
from saliweb.backend import Database, Job, MySQLField

def utc_timestamp():
    # sqlite doesn't have a datetime type, so we use float
    # instead (seconds-since-epoch) for testing
    return time.time()

class MemoryDatabase(Database):
    """Subclass that uses an in-memory SQLite3 database rather than MySQL"""
    def _connect(self, config):
        self._placeholder = '?'
        self.conn = sqlite3.connect(':memory:')
        # sqlite has no date/time functions, unlike MySQL, so add basic ones
        self.conn.create_function('UTC_TIMESTAMP', 0, utc_timestamp)

def make_test_jobs(sql):
    c = sql.cursor()
    timenow = time.time()
    c.execute("INSERT INTO INCOMING(name,runjob_id,submit_time,expire_time) " \
              + "VALUES(?,?,?,?)",
              ('job1', 'SGE-job-1', timenow, timenow + 1000.))
    c.execute("INSERT INTO RUNNING(name,runjob_id,submit_time,expire_time) " \
              + "VALUES(?,?,?,?)",
              ('job2', 'SGE-job-2', timenow, timenow + 1000.))
    c.execute("INSERT INTO RUNNING(name,runjob_id,submit_time,expire_time) " \
              + "VALUES(?,?,?,?)",
              ('job3', 'SGE-job-3', timenow, timenow - 1000.))
    sql.commit()

class DatabaseTest(unittest.TestCase):
    """Check Database class"""

    def test_init(self):
        """Check Database init"""
        db = MemoryDatabase(Job)
        self.assertEqual(len(db._fields), 13)
        self.assertEqual(db._fields[0].name, 'name')

    def test_add_field(self):
        """Check Database.add_field()"""
        db = MemoryDatabase(Job)
        numfields = len(db._fields)
        db.add_field(MySQLField('test_field', 'TEXT'))
        self.assertEqual(len(db._fields), numfields + 1)
        self.assertEqual(db._fields[-1].name, 'test_field')

    def test_create_tables(self):
        """Make sure that Database.create_tables() makes tables"""
        db = MemoryDatabase(Job)
        db._connect(None)
        db.create_tables()
        c = db.conn.cursor()
        c.execute('DROP TABLE INCOMING')
        self.assertRaises(sqlite3.OperationalError, c.execute,
                          'DROP TABLE GARBAGE')
        db.conn.commit()

    def test_delete_tables(self):
        """Check Database.delete_tables()"""
        db = MemoryDatabase(Job)
        db._connect(None)
        c = db.conn.cursor()
        c.execute('CREATE TABLE INCOMING (test TEXT)')
        db.conn.commit()
        # Should work regardless of whether tables exist
        db.delete_tables()
        # It should have deleted the INCOMING table
        self.assertRaises(sqlite3.OperationalError, c.execute,
                          'DROP TABLE INCOMING')

    def test_get_jobs(self):
        """Check Database.get_all_jobs_in_state()"""
        db = MemoryDatabase(Job)
        db._connect(None)
        db.create_tables()
        make_test_jobs(db.conn)
        jobs = list(db.get_all_jobs_in_state('INCOMING'))
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]._jobdict['name'], 'job1')
        self.assertEqual(jobs[0]._jobdict['runjob_id'], 'SGE-job-1')
        jobs = list(db.get_all_jobs_in_state('RUNNING'))
        self.assertEqual(len(jobs), 2)
        jobs = list(db.get_all_jobs_in_state('INCOMING', name='job1'))
        self.assertEqual(len(jobs), 1)
        jobs = list(db.get_all_jobs_in_state('INCOMING', name='job2'))
        self.assertEqual(len(jobs), 0)
        jobs = list(db.get_all_jobs_in_state('INCOMING',
                                             after_time='expire_time'))
        self.assertEqual(len(jobs), 0)
        jobs = list(db.get_all_jobs_in_state('RUNNING',
                                             after_time='expire_time'))
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]._jobdict['name'], 'job3')

    def test_change_job_state(self):
        """Check Database._change_job_state()"""
        db = MemoryDatabase(Job)
        db._connect(None)
        db.create_tables()
        make_test_jobs(db.conn)
        job = list(db.get_all_jobs_in_state('INCOMING'))[0]
        # side effect: should update _jobdict
        job._jobdict['runjob_id'] = 'new-SGE-ID'
        db._change_job_state(job._jobdict, 'INCOMING', 'PREPROCESSING')
        jobs = list(db.get_all_jobs_in_state('INCOMING'))
        self.assertEqual(len(jobs), 0)
        jobs = list(db.get_all_jobs_in_state('PREPROCESSING'))
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]._jobdict['runjob_id'], 'new-SGE-ID')

    def test_update_job(self):
        """Check Database._update_job()"""
        db = MemoryDatabase(Job)
        db._connect(None)
        db.create_tables()
        make_test_jobs(db.conn)
        job = list(db.get_all_jobs_in_state('INCOMING'))[0]
        job._jobdict['runjob_id'] = 'new-SGE-ID'
        db._update_job(job._jobdict, 'INCOMING')
        # Get a fresh copy of the job from the database
        newjob = list(db.get_all_jobs_in_state('INCOMING'))[0]
        self.assert_(job is not newjob)
        self.assertEqual(newjob._jobdict['runjob_id'], 'new-SGE-ID')

if __name__ == '__main__':
    unittest.main()
