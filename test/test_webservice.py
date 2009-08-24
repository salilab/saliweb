import unittest
from test_database import make_test_jobs
from memory_database import MemoryDatabase
from saliweb.backend import WebService, Config, Job

class WebServiceTest(unittest.TestCase):
    """Check WebService class"""

    def test_init(self):
        """Check WebService init"""
        db = MemoryDatabase(Job)
        c = Config(None)
        ws = WebService(c, db)

    def test_get_job_by_name(self):
        """Check WebService.get_job_by_name()"""
        db = MemoryDatabase(Job)
        c = Config(None)
        ws = WebService(c, db)
        db.create_tables()
        make_test_jobs(db.conn)
        job = ws.get_job_by_name('RUNNING', 'job3')
        self.assertEqual(job.name, 'job3')
        job = ws.get_job_by_name('RUNNING', 'job9')
        self.assertEqual(job, None)


if __name__ == '__main__':
    unittest.main()
