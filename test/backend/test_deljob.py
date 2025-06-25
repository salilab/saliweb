import unittest
import sys
from saliweb.backend import InvalidStateError
from saliweb.backend.deljob import check_valid_state, get_options, delete_job
from saliweb.backend.deljob import main
from io import StringIO


class DummyWeb(object):
    def __init__(self, pid):
        self.pid = pid

    def get_running_pid(self):
        return self.pid


class DelJobTest(unittest.TestCase):
    """Check deljob script"""

    def test_check_valid_state(self):
        """Test check_valid_state function"""
        web = DummyWeb(None)
        self.assertRaises(InvalidStateError, check_valid_state, web, 'garbage')
        self.assertRaises(InvalidStateError, check_valid_state, web, 'failed')
        for state in ('FAILED', 'EXPIRED', 'COMPLETED', 'RUNNING'):
            check_valid_state(web, state)

        # Only FAILED/EXPIRED OK if the web service is running
        web = DummyWeb(999)
        for state in ('FAILED', 'EXPIRED'):
            check_valid_state(web, state)
        for state in ('COMPLETED', 'RUNNING'):
            self.assertRaises(ValueError, check_valid_state, web, state)

    def test_get_options(self):
        """Test deljob get_options()"""
        def run_get_options(args):
            old = sys.argv
            oldstderr = sys.stderr
            try:
                sys.stderr = StringIO()
                sys.argv = ['testprogram'] + args
                return get_options()
            finally:
                sys.stderr = oldstderr
                sys.argv = old
        self.assertRaises(SystemExit, run_get_options, [])
        state, jobnames, force = run_get_options(['FAILED', 'testjob1',
                                                  'job2'])
        self.assertEqual(state, 'FAILED')
        self.assertEqual(jobnames, ['testjob1', 'job2'])
        self.assertEqual(force, False)
        for arg in ['-f', '--force']:
            state, jobnames, force = run_get_options([arg, 'FAILED',
                                                      'testjob'])
            self.assertEqual(force, True)
            self.assertEqual(jobnames, ['testjob'])

    def test_delete_job(self):
        """Test deljob delete_job()"""
        class DummyJob(object):
            deleted = False
            name = 'testjob'

            def delete(self):
                self.deleted = True

        class DummyStdin(object):
            def __init__(self, answer):
                self.answer = answer

            def readline(self):
                return self.answer

        def run_delete_job(job, force, answer):
            oldout = sys.stdout
            oldin = sys.stdin
            try:
                sio = StringIO()
                sys.stdout = sio
                sys.stdin = DummyStdin(answer)
                delete_job(job, force)
                return sio.getvalue()
            finally:
                sys.stdout = oldout
                sys.stdin = oldin
        j = DummyJob()
        out = run_delete_job(j, True, None)
        self.assertEqual(j.deleted, True)
        self.assertEqual(out, '')
        for no in ('', 'n', 'x'):
            j = DummyJob()
            out = run_delete_job(j, False, no)
            self.assertEqual(j.deleted, False)
            self.assertEqual(out, 'Delete job testjob? ')
        for yes in ('y', 'Y', 'yes'):
            j = DummyJob()
            out = run_delete_job(j, False, yes)
            self.assertEqual(j.deleted, True)
            self.assertEqual(out, 'Delete job testjob? ')

    def test_main(self):
        """Test deljob main()"""
        class DummyJob(object):
            def __init__(self, mod):
                self.mod = mod

            def delete(self):
                self.mod.job_deleted = True

        class DummyWebService(object):
            def __init__(self, mod):
                self.mod = mod

            def get_running_pid(self):
                return 9999

            def get_job_by_name(self, state, name):
                if state == 'FAILED' and name == 'testjob':
                    return DummyJob(self.mod)
                else:
                    return None

        class DummyModule(object):
            config = 'testconfig'
            job_deleted = False

            def get_web_service(self, config):
                return DummyWebService(self)

        old = sys.argv
        olderr = sys.stderr
        try:
            sio = StringIO()
            sys.stderr = sio
            mod = DummyModule()
            sys.argv = ['testprogram'] + ['-f', 'FAILED', 'badjob']
            main(mod)
            self.assertIn('Could not find job badjob\n', sio.getvalue())
            self.assertEqual(mod.job_deleted, False)

            sio = StringIO()
            sys.stderr = sio
            mod = DummyModule()
            sys.argv = ['testprogram'] + ['-f', 'FAILED', 'testjob']
            main(mod)
            self.assertEqual(sio.getvalue(), '')
            self.assertEqual(mod.job_deleted, True)
        finally:
            sys.argv = old
            sys.stderr = olderr


if __name__ == '__main__':
    unittest.main()
