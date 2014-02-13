import unittest
from StringIO import StringIO
import saliweb.backend.events
from saliweb.backend import SGERunner, SaliSGERunner, Job
import sys
import re
import os
import time
import shutil
import tempfile

class BrokenRunner(SGERunner):
    # Duplicate runner name, so it shouldn't work
    _runner_name = 'qb3sge'


class DummyDRMAAModule(object):
    class InvalidJobException(Exception): pass
    class Session(object):
        TIMEOUT_WAIT_FOREVER = 'forever'

class DummyDRMAASession(object):
    def jobStatus(self, jobid):
        if jobid == 'donejob' or re.match('donebulk\.\d+', jobid) \
           or jobid == 'runningbulk.5':
            raise DummyDRMAAModule.InvalidJobException()
        elif jobid == 'runningjob' or re.match('runningbulk\.\d+', jobid):
            return 'running'
        elif jobid == 'queuedjob':
            return 'queued'
        else:
            raise RuntimeError("Bad jobid: " + jobid)
    def createJobTemplate(self):
        class Dummy(object): pass
        return Dummy()
    def deleteJobTemplate(self, jt):
        DummyDRMAASession.deleted_template = jt
    def runBulkJobs(self, jt, first, last, step):
        return ['dummyJob.%d' % x for x in range(first, last+step, step)]
    def runJob(self, jt):
        return 'dummyJob'
    def synchronize(self, jobids, timeout, cleanup):
        pass
    def wait(self, jobids, timeout):
        return True

class TestRunner(SGERunner):
    @classmethod
    def _get_drmaa(cls):
        return DummyDRMAAModule(), DummyDRMAASession()

class RunnerTest(unittest.TestCase):
    """Check Runner classes"""

    def test_duplicate_runner_names(self):
        """Make sure that duplicate Runner names aren't accepted"""
        self.assertRaises(TypeError, Job.register_runner_class, BrokenRunner)

    def test_generate_script(self):
        """Check that SGERunner generates reasonable scripts"""
        for runner in (SGERunner, SaliSGERunner):
            r = runner('echo foo', interpreter='/bin/csh')
            r.set_sge_options('-l diva1=1G')
            sio = StringIO()
            r._write_sge_script(sio)
            expected = """#!/bin/csh
#$ -S /bin/csh
#$ -cwd
#$ -l diva1=1G
setenv _SALI_JOB_DIR `pwd`
echo "STARTED" > ${_SALI_JOB_DIR}/job-state
echo foo
echo "DONE" > ${_SALI_JOB_DIR}/job-state
"""
            self.assertEqual(sio.getvalue(), expected)

    def test_check_completed(self):
        """Check SGERunner._check_completed()"""
        TestRunner._waited_jobs.add('waitedjob')
        self.assertEqual(TestRunner._check_completed('donejob', ''), True)
        self.assertEqual(TestRunner._check_completed('runningjob', ''), False)
        self.assertEqual(TestRunner._check_completed('donebulk.1-10:1', ''),
                         True)
        self.assertEqual(TestRunner._check_completed('runningbulk.1-10:1', ''),
                         False)
        self.assertEqual(TestRunner._check_completed('queuedjob', ''), False)
        self.assertEqual(TestRunner._check_completed('waitedjob', ''), False)

    def test_get_drmaa(self):
        """Check SGERunner._get_drmaa()"""
        class DummyDRMAA(object):
            class Session(object):
                def initialize(self): pass
                def exit(self): pass
        sys.modules['drmaa'] = DummyDRMAA()
        r = SGERunner('test.sh')
        d, s = r._get_drmaa()
        self.assert_(isinstance(d, DummyDRMAA))
        self.assert_(isinstance(s, DummyDRMAA.Session))
        SGERunner._drmaa = None
        del sys.modules['drmaa']

    def test_check_run(self):
        """Check SGERunner._qsub()"""
        class DummyWebService(object):
            def __init__(self):
                self._event_queue = saliweb.backend.events._EventQueue()
        ws = DummyWebService()
        r = TestRunner('echo foo')
        jobid1 = r._qsub('test.sh', ws)
        self.assertEqual(jobid1, 'dummyJob')
        jt = DummyDRMAASession.deleted_template
        self.assertEqual(jt.nativeSpecification, ' -w n -b no')
        self.assertEqual(jt.remoteCommand, 'test.sh')
        self.assertEqual(jt.workingDirectory, r._directory)

        r = TestRunner('echo foo')
        r.set_sge_options('-t 2-10:2')
        jobid2 = r._qsub('test.sh', ws)
        self.assertEqual(jobid2, 'dummyJob.2-10:2')
        jt = DummyDRMAASession.deleted_template
        self.assertEqual(jt.nativeSpecification, '-t 2-10:2 -w n -b no')
        self.assertEqual(jt.remoteCommand, 'test.sh')
        self.assertEqual(jt.workingDirectory, r._directory)

        # Make sure the waiter threads get time to finish
        time.sleep(0.1)
        e1 = ws._event_queue.get(timeout=0.)
        e2 = ws._event_queue.get(timeout=0.)
        e3 = ws._event_queue.get(timeout=0.)
        self.assertNotEqual(e1, None)
        self.assertNotEqual(e2, None)
        self.assertEqual(e3, None)

if __name__ == '__main__':
    unittest.main()
