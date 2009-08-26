import unittest
from test_database import make_test_jobs
from memory_database import MemoryDatabase
from saliweb.backend import WebService, Config, Job
from StringIO import StringIO

basic_config = """
[general]
admin_email: test@salilab.org
service_name: test_service
state_file: state_file

[database]
user: dbuser
db: testdb
passwd: dbtest

[directories]
incoming: /
preprocessing: /

[oldjobs]
archive: 30d
expire: 90d
"""

job_log = []
class LoggingJob(Job):
    """Test Job subclass that logs which methods are called"""
    def _try_run(self): job_log.append((self.name, 'run'))
    def _try_complete(self): job_log.append((self.name, 'complete'))
    def _try_archive(self): job_log.append((self.name, 'archive'))
    def _try_expire(self): job_log.append((self.name, 'expire'))


class WebServiceTest(unittest.TestCase):
    """Check WebService class"""

    def _setup_webservice(self):
        db = MemoryDatabase(LoggingJob)
        conf = Config(StringIO(basic_config))
        web = WebService(conf, db)
        db.create_tables()
        make_test_jobs(db.conn)
        return db, conf, web

    def test_init(self):
        """Check WebService init"""
        db = MemoryDatabase(Job)
        conf = Config(StringIO(basic_config))
        ws = WebService(conf, db)

    def test_get_job_by_name(self):
        """Check WebService.get_job_by_name()"""
        db, conf, web = self._setup_webservice()
        job = web.get_job_by_name('RUNNING', 'job3')
        self.assertEqual(job.name, 'job3')
        job = web.get_job_by_name('RUNNING', 'job9')
        self.assertEqual(job, None)

    def test_process_incoming(self):
        """Check WebService.process_incoming_jobs()"""
        global job_log
        job_log = []
        db, conf, web = self._setup_webservice()
        web.process_incoming_jobs()
        self.assertEqual(job_log, [('job1', 'run')])

    def test_process_completed(self):
        """Check WebService.process_completed_jobs()"""
        global job_log
        job_log = []
        db, conf, web = self._setup_webservice()
        web.process_completed_jobs()
        self.assertEqual(job_log, [('job2', 'complete'), ('job3', 'complete')])

    def test_process_old(self):
        """Check WebService.process_old_jobs()"""
        global job_log
        job_log = []
        db, conf, web = self._setup_webservice()
        web.process_old_jobs()
        self.assertEqual(job_log, [(u'ready-for-archive', 'archive'),
                                   (u'ready-for-expire', 'expire')])

    def test_all_processing(self):
        """Check WebService.do_all_processing()"""
        global job_log
        job_log = []
        db, conf, web = self._setup_webservice()
        web.do_all_processing()
        self.assertEqual(job_log, [('job1', 'run'),
                                   ('job2', 'complete'), ('job3', 'complete'),
                                   (u'ready-for-archive', 'archive'),
                                   (u'ready-for-expire', 'expire')])

if __name__ == '__main__':
    unittest.main()
