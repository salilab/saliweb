import unittest
try:
    import sqlite3
except:
    from pysqlite2 import dbapi2 as sqlite3
import datetime
from saliweb.backend import Job, MySQLField
import saliweb.backend
from memory_database import MemoryDatabase

def make_test_jobs(sql):
    c = sql.cursor()
    utcnow = datetime.datetime.utcnow()
    c.execute("INSERT INTO jobs(name,state,runner_id,submit_time, " \
              + "expire_time,directory,url) VALUES(?,?,?,?,?,?,?)",
              ('job1', 'INCOMING', 'SGE-job-1', utcnow,
               utcnow + datetime.timedelta(days=1), '/', 'http://testurl'))
    c.execute("INSERT INTO jobs(name,state,runner_id,submit_time, " \
              + "expire_time,directory,url) VALUES(?,?,?,?,?,?,?)",
              ('job2', 'RUNNING', 'salisge:job-2',
               utcnow + datetime.timedelta(hours=1),
               utcnow + datetime.timedelta(days=1), '/', 'http://testurl'))
    c.execute("INSERT INTO jobs(name,state,runner_id,submit_time, " \
              + "expire_time,directory,url) VALUES(?,?,?,?,?,?,?)",
              ('job3', 'RUNNING', 'SGE-job-3', utcnow,
               utcnow - datetime.timedelta(days=1), '/', 'http://testurl'))
    c.execute("INSERT INTO jobs(name,state,runner_id,submit_time, " \
              + "archive_time,expire_time,directory,url) " \
              + "VALUES(?,?,?,?,?,?,?,?)",
              ('preproc', 'PREPROCESSING', None, utcnow, utcnow, utcnow,
               '/', 'http://testurl'))
    c.execute("INSERT INTO jobs(name,state,runner_id,submit_time, " \
              + "archive_time,expire_time,directory,url) " \
              + "VALUES(?,?,?,?,?,?,?,?)",
              ('postproc', 'POSTPROCESSING', None, utcnow, utcnow, utcnow,
               '/', 'http://testurl'))
    c.execute("INSERT INTO jobs(name,state,runner_id,submit_time, " \
              + "archive_time,expire_time,directory,url) " \
              + "VALUES(?,?,?,?,?,?,?,?)",
              ('ready-for-archive', 'COMPLETED', None, utcnow,
               utcnow - datetime.timedelta(days=1),
               utcnow + datetime.timedelta(days=1), '/', 'http://testurl'))
    c.execute("INSERT INTO jobs(name,state,runner_id,submit_time, " \
              + "archive_time,expire_time,directory,url) " \
              + "VALUES(?,?,?,?,?,?,?,?)",
              ('ready-for-expire', 'ARCHIVED', None, utcnow,
               utcnow + datetime.timedelta(days=1),
               utcnow - datetime.timedelta(days=1), '/', 'http://testurl'))
    c.execute("INSERT INTO jobs(name,state,runner_id,submit_time, " \
              + "archive_time,expire_time,directory,url) " \
              + "VALUES(?,?,?,?,?,?,?,?)",
              ('never-archive', 'COMPLETED', None, utcnow,
               None, None, '/', 'http://testurl'))
    sql.commit()

class DatabaseTest(unittest.TestCase):
    """Check Database class"""

    def test_init(self):
        """Check Database init"""
        db = MemoryDatabase(Job)
        self.assertEqual(len(db._fields), 16)
        self.assertEqual(db._fields[0].name, 'name')

    def test_connect(self):
        """Check the Database._config() method"""
        class DummyConfig(object):
            database = {'user': 'testuser', 'db': 'testdb', 'passwd': 'testpwd',
                        'socket': 'foo'}
        config = DummyConfig()
        db = saliweb.backend.Database(Job)
        db._connect(config)
        self.assertEqual(db._OperationalError, 'Dummy MySQL OperationalError')
        self.assertEqual(db._placeholder, '%s')
        self.assertEqual(db.config, config)
        self.assertEqual(db.conn.sql,
                    ['SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED'])
        self.assertEqual(db.conn.args, ())
        self.assertEqual(db.conn.keys, {'user':'testuser',
                                        'db':'testdb',
                                        'unix_socket':'foo',
                                        'passwd':'testpwd'})

    def test_add_field(self):
        """Check Database.add_field()"""
        db = MemoryDatabase(Job)
        numfields = len(db._fields)
        db.add_field(MySQLField('test_field', 'TEXT'))
        self.assertEqual(len(db._fields), numfields + 1)
        self.assertEqual(db._fields[-1].name, 'test_field')

    def test_set_track_hostname(self):
        """Test Database.set_track_hostname()"""
        db = MemoryDatabase(Job)
        numfields = len(db._fields)
        db.set_track_hostname()
        self.assertEqual(len(db._fields), numfields + 1)
        self.assertEqual(db._fields[-1].name, 'hostname')

    def test_create_tables(self):
        """Make sure that Database._create_tables() makes tables and indexes"""
        db = MemoryDatabase(Job)
        db._connect(None)
        db._create_tables()
        c = db.conn.cursor()
        c.execute('DROP INDEX state_index')
        for bad_index in ('GARBAGE', 'state', 'name_index'):
            self.assertRaises(sqlite3.OperationalError, c.execute,
                              'DROP INDEX ' + bad_index)
        c.execute('DROP TABLE jobs')
        c.execute('DROP TABLE dependencies')
        self.assertRaises(sqlite3.OperationalError, c.execute,
                          'DROP TABLE GARBAGE')
        db.conn.commit()

    def test_execute(self):
        """Test Database._execute method"""
        class DummyError(Exception):
            pass

        class DummyCursor(object):
            def __init__(self, conn):
                self.conn = conn
            def execute(self, query, args):
                if query == 'execute exception':
                    raise DummyError((0, 'normal error'))
                elif query == 'reconnect fail':
                    raise DummyError(2006, 'MySQL server has gone away')
                elif query == 'reconnect succeeds' \
                     and not self.conn.db.in_query:
                    self.conn.db.in_query = True # Prevent reraise
                    raise DummyError(2006, 'MySQL server has gone away')

        class DummyConnection(object):
            def __init__(self, db):
                self.db = db
            def cursor(self):
                return DummyCursor(self)

        class DummyDatabase(saliweb.backend.Database):
            in_query = False
            def add_field(self, field):
                pass
            def _connect(self, config):
                self.config = config
                self._OperationalError = DummyError
                self.conn = DummyConnection(self)

        db = DummyDatabase(None)
        db._connect(None)
        # Regular exceptions should be propagated
        self.assertRaises(DummyError, db._execute, 'execute exception')
        # Return value should be the cursor
        c = db._execute('CREATE TABLE jobs (test TEXT)')
        self.assert_(isinstance(c, DummyCursor))

        # If a 'gone away' error is encountered and reraised, the connection
        # should have been reestablished
        oldconn = db.conn
        self.assertRaises(DummyError, db._execute, 'reconnect fail')
        self.assertNotEqual(id(db.conn), id(oldconn))

        # A successful reconnect should not raise an exception but should
        # reeestablish the connection
        oldconn = db.conn
        c = db._execute('reconnect succeeds')
        self.assertNotEqual(id(db.conn), id(oldconn))
        self.assert_(isinstance(c, DummyCursor))

    def test_drop_tables(self):
        """Check Database._drop_tables()"""
        db = MemoryDatabase(Job)
        db._connect(None)
        c = db.conn.cursor()
        c.execute('CREATE TABLE jobs (test TEXT)')
        c.execute('CREATE TABLE dependencies (test TEXT)')
        db.conn.commit()
        db._drop_tables()
        # Should work regardless of whether tables exist
        db._drop_tables()
        # It should have deleted the tables and state index
        self.assertRaises(sqlite3.OperationalError, c.execute,
                          'DROP TABLE jobs')
        self.assertRaises(sqlite3.OperationalError, c.execute,
                          'DROP TABLE dependencies')
        self.assertRaises(sqlite3.OperationalError, c.execute,
                          'DROP INDEX state_index')

    def test_count_jobs(self):
        """Check Database._count_all_jobs_in_state()"""
        db = MemoryDatabase(Job)
        db._connect(None)
        db._create_tables()
        make_test_jobs(db.conn)
        self.assertEqual(db._count_all_jobs_in_state('INCOMING'), 1)
        self.assertEqual(db._count_all_jobs_in_state('RUNNING'), 2)
        self.assertEqual(db._count_all_jobs_in_state('EXPIRED'), 0)

    def test_order_by(self):
        """Test Database._get_all_jobs_in_state() order_by parameter"""
        db = MemoryDatabase(Job)
        db._connect(None)
        db._create_tables()
        make_test_jobs(db.conn)
        jobs = list(db._get_all_jobs_in_state('RUNNING'))
        # Jobs should come out in the same order they were inserted
        self.assertEqual([x._metadata['name'] for x in jobs], ['job2', 'job3'])

        jobs = list(db._get_all_jobs_in_state('RUNNING',
                                              order_by='submit_time'))
        # Jobs should be sorted by submit time
        self.assertEqual([x._metadata['name'] for x in jobs], ['job3', 'job2'])

    def test_get_jobs(self):
        """Check Database._get_all_jobs_in_state()"""
        db = MemoryDatabase(Job)
        db._connect(None)
        db._create_tables()
        make_test_jobs(db.conn)
        jobs = list(db._get_all_jobs_in_state('INCOMING'))
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]._metadata['name'], 'job1')
        self.assertEqual(jobs[0]._metadata['runner_id'], 'SGE-job-1')
        jobs = list(db._get_all_jobs_in_state('RUNNING'))
        self.assertEqual(len(jobs), 2)
        jobs = list(db._get_all_jobs_in_state('INCOMING', name='job1'))
        self.assertEqual(len(jobs), 1)
        jobs = list(db._get_all_jobs_in_state('INCOMING', name='job2'))
        self.assertEqual(len(jobs), 0)
        jobs = list(db._get_all_jobs_in_state('INCOMING',
                                              after_time='expire_time'))
        self.assertEqual(len(jobs), 0)
        jobs = list(db._get_all_jobs_in_state('RUNNING',
                                              after_time='expire_time'))
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]._metadata['name'], 'job3')
        jobs = list(db._get_all_jobs_in_state('COMPLETED',
                                              after_time='expire_time'))
        self.assertEqual(len(jobs), 0)

    def test_change_job_state(self):
        """Check Database._change_job_state()"""
        db = MemoryDatabase(Job)
        db._connect(None)
        db._create_tables()
        make_test_jobs(db.conn)
        job = list(db._get_all_jobs_in_state('INCOMING'))[0]
        # side effect: should update _metadata
        job._metadata['runner_id'] = 'new-SGE-ID'
        db._change_job_state(job._metadata, 'INCOMING', 'FAILED')
        jobs = list(db._get_all_jobs_in_state('INCOMING'))
        self.assertEqual(len(jobs), 0)
        jobs = list(db._get_all_jobs_in_state('FAILED'))
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]._metadata['runner_id'], 'new-SGE-ID')

    def test_update_job(self):
        """Check Database._update_job()"""
        db = MemoryDatabase(Job)
        db._connect(None)
        db._create_tables()
        make_test_jobs(db.conn)
        job = list(db._get_all_jobs_in_state('INCOMING'))[0]
        job._metadata['runner_id'] = 'new-SGE-ID'
        db._update_job(job._metadata, 'INCOMING')
        # Get a fresh copy of the job from the database
        newjob = list(db._get_all_jobs_in_state('INCOMING'))[0]
        self.assert_(job is not newjob)
        self.assertEqual(newjob._metadata['runner_id'], 'new-SGE-ID')

if __name__ == '__main__':
    unittest.main()
