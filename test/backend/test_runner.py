from __future__ import print_function
import unittest
import sys
if sys.version_info[0] >= 3:
    from io import StringIO
else:
    from io import BytesIO as StringIO
import saliweb.backend.events
from saliweb.backend import SGERunner, WyntonSGERunner, Job
from saliweb.backend import SLURMRunner, _LockedJobDict
import testutil
import os
import time


class BrokenRunner(SGERunner):
    # Duplicate runner name, so it shouldn't work
    _runner_name = 'wyntonsge'


class DummyDRMAAModule(object):
    class InvalidJobException(Exception):
        pass

    class Session(object):
        TIMEOUT_WAIT_FOREVER = 'forever'


class DummyDRMAASession(object):
    def jobStatus(self, jobid):
        if jobid == 'donejob':
            raise DummyDRMAAModule.InvalidJobException()
        elif jobid == 'runningjob':
            return 'running'
        elif jobid == 'queuedjob':
            return 'queued'
        else:
            raise RuntimeError("Bad jobid: " + jobid)

    def createJobTemplate(self):
        class Dummy(object):
            pass
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


class TestRunner(WyntonSGERunner):
    @classmethod
    def _get_drmaa(cls):
        return DummyDRMAAModule(), DummyDRMAASession()


class TestSLURMRunner(SLURMRunner):
    _waited_jobs = _LockedJobDict()
    _env = {}

    @classmethod
    def _get_drmaa(cls):
        return DummyDRMAAModule(), DummyDRMAASession()


class RunnerTest(unittest.TestCase):
    """Check Runner classes"""

    def test_duplicate_runner_names(self):
        """Make sure that duplicate Runner names aren't accepted"""
        self.assertRaises(TypeError, Job.register_runner_class, BrokenRunner)

    def test_sge_name(self):
        """Check SGERunner.set_name()"""
        r = SGERunner('echo foo', interpreter='/bin/csh')
        r.set_name('test\t job ')
        self.assertEqual(r._name, 'testjob')
        r.set_name('TestJob')
        self.assertEqual(r._name, 'TestJob')
        r.set_name('1234')
        self.assertEqual(r._name, 'J1234')
        r.set_name('None')
        self.assertEqual(r._name, 'JNone')
        r.set_name('ALL')
        self.assertEqual(r._name, 'JALL')
        r.set_name('template')
        self.assertEqual(r._name, 'Jtemplate')

    def test_slurm_name(self):
        """Check SLURMRunner.set_name()"""
        r = SLURMRunner('echo foo', interpreter='/bin/csh')
        r.set_name('test\t job ')
        self.assertEqual(r._name, 'testjob')
        r.set_name('TestJob')
        self.assertEqual(r._name, 'TestJob')
        r.set_name('1234')
        self.assertEqual(r._name, '1234')
        r.set_name('None')
        self.assertEqual(r._name, 'None')
        r.set_name('ALL')
        self.assertEqual(r._name, 'ALL')
        r.set_name('template')
        self.assertEqual(r._name, 'template')

    def test_sge_generate_script(self):
        """Check that SGERunner generates reasonable scripts"""
        for runner in (WyntonSGERunner,):
            r = runner('echo foo', interpreter='/bin/csh')
            r.set_options('-l diva1=1G')
            r.set_name('test\t job ')
            sio = StringIO()
            r._write_script(sio)
            expected = """#!/bin/csh
#$ -S /bin/csh
#$ -cwd
#$ -l diva1=1G
#$ -N testjob
setenv _SALI_JOB_DIR `pwd`
echo "STARTED" > ${_SALI_JOB_DIR}/job-state
echo foo
echo "DONE" > ${_SALI_JOB_DIR}/job-state
"""
            self.assertEqual(sio.getvalue(), expected)
            r = runner('echo foo', interpreter='/bin/oddshell')
            sio = StringIO()
            r._write_script(sio)
            expected = """#!/bin/oddshell
#$ -S /bin/oddshell
#$ -cwd
echo foo
"""
            self.assertEqual(sio.getvalue(), expected)

    def test_slurm_generate_script(self):
        """Check that SLURMRunner generates reasonable scripts"""
        for runner in (SLURMRunner,):
            r = runner('echo foo', interpreter='/bin/csh')
            r.set_options('-l diva1=1G')
            r.set_name('test\t job ')
            sio = StringIO()
            r._write_script(sio)
            expected = """#!/bin/csh
#SBATCH -l diva1=1G
#SBATCH -J testjob
setenv _SALI_JOB_DIR `pwd`
echo "STARTED" > ${_SALI_JOB_DIR}/job-state
echo foo
echo "DONE" > ${_SALI_JOB_DIR}/job-state
"""
            self.assertEqual(sio.getvalue(), expected)
            r = runner('echo foo', interpreter='/bin/oddshell')
            sio = StringIO()
            r._write_script(sio)
            expected = """#!/bin/oddshell
echo foo
"""
            self.assertEqual(sio.getvalue(), expected)

    @testutil.run_in_tempdir
    def test_check_completed(self):
        """Check SGERunner._check_completed()"""
        TestRunner._waited_jobs.add('waitedjob')
        qstat = open('qstat', 'w')
        qstat.write("""#!%s
from __future__ import print_function
import sys
if sys.argv[2].startswith('badbulk'):
    sys.exit(1)
elif sys.argv[2].startswith('donebulk'):
    print("Following jobs do not exist:")
    print(sys.argv[2])
    sys.exit(1)
else:
    print("job info")
""" % sys.executable)
        qstat.close()
        os.chmod('qstat', 0o755)
        TestRunner._qstat = os.path.join(os.getcwd(), 'qstat')
        self.assertEqual(TestRunner._check_completed('donejob', ''), True)
        self.assertEqual(TestRunner._check_completed('runningjob', ''), False)
        self.assertEqual(TestRunner._check_completed('donebulk.1-10:1', ''),
                         True)
        self.assertRaises(OSError, TestRunner._check_completed,
                          'badbulk.1-10:1', '')
        self.assertEqual(TestRunner._check_completed('runningbulk.1-10:1', ''),
                         False)
        self.assertEqual(TestRunner._check_completed('queuedjob', ''), False)
        self.assertEqual(TestRunner._check_completed('waitedjob', ''), False)

    @testutil.run_in_tempdir
    def test_slurm_check_completed(self):
        """Check SLURMRunner._check_completed()"""
        TestSLURMRunner._waited_jobs.add('waitedjob')
        with open('squeue', 'w') as squeue:
            squeue.write("""#!%s
from __future__ import print_function
import sys
if sys.argv[2].startswith('badbulk'):
    sys.exit(1)
elif sys.argv[2].startswith('donebulk'):
    print("slurm_load_jobs error: Invalid job id specified")
    sys.exit(1)
else:
    print("job info")
""" % sys.executable)
        os.chmod('squeue', 0o755)
        TestSLURMRunner._squeue = os.path.join(os.getcwd(), 'squeue')
        self.assertEqual(TestSLURMRunner._check_completed('donejob', ''), True)
        self.assertEqual(TestSLURMRunner._check_completed('runningjob', ''),
                         False)
        self.assertEqual(
            TestSLURMRunner._check_completed('donebulk_1-10:1', ''), True)
        self.assertRaises(OSError, TestSLURMRunner._check_completed,
                          'badbulk_1-10:1', '')
        self.assertEqual(
            TestSLURMRunner._check_completed('runningbulk_1-10:1', ''), False)
        self.assertEqual(TestSLURMRunner._check_completed('queuedjob', ''),
                         False)
        self.assertEqual(TestSLURMRunner._check_completed('waitedjob', ''),
                         False)

    def test_get_drmaa(self):
        """Check SGERunner._get_drmaa()"""
        class DummyDRMAA(object):
            class Session(object):
                def initialize(self): pass
                def exit(self): pass
        sys.modules['drmaa'] = DummyDRMAA()
        r = WyntonSGERunner('test.sh')
        d, s = r._get_drmaa()
        self.assertIsInstance(d, DummyDRMAA)
        self.assertIsInstance(s, DummyDRMAA.Session)
        SGERunner._drmaa = None
        del sys.modules['drmaa']

    def test_check_run(self):
        """Check SGERunner._qsub() and _run()"""
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

        with testutil.temp_dir() as tmpdir:
            r = TestRunner('echo foo')
            r._directory = tmpdir
            r.set_options('-t 2-10:2')
            jobid2 = r._run(ws)
            self.assertEqual(jobid2, 'dummyJob.2-10:2')
            jt = DummyDRMAASession.deleted_template
            self.assertEqual(jt.nativeSpecification, '-t 2-10:2 -w n -b no')
            self.assertEqual(jt.remoteCommand,
                             os.path.join(tmpdir, 'sge-script.sh'))
            self.assertEqual(jt.workingDirectory, r._directory)

        # Make sure the waiter threads get time to finish
        time.sleep(0.1)
        e1 = ws._event_queue.get(timeout=0.)
        e2 = ws._event_queue.get(timeout=0.)
        e3 = ws._event_queue.get(timeout=0.)
        self.assertIsNotNone(e1)
        self.assertIsNotNone(e2)
        self.assertIsNone(e3)


if __name__ == '__main__':
    unittest.main()
