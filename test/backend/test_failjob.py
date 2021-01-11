import unittest
import sys
from saliweb.backend.failjob import check_daemon_running, get_options, fail_job
from saliweb.backend.failjob import main
if sys.version_info[0] >= 3:
    from io import StringIO
else:
    from io import BytesIO as StringIO


class DummyWeb(object):
    def __init__(self, pid):
        self.pid = pid

    def get_running_pid(self):
        return self.pid


class FailJobTest(unittest.TestCase):
    """Check failjob script"""

    def test_check_daemon_running(self):
        """Test check_daemon_running function"""
        # Should fail if the daemon is running
        web = DummyWeb(None)
        check_daemon_running(web)
        web = DummyWeb(999)
        self.assertRaises(ValueError, check_daemon_running, web)

    def test_get_options(self):
        """Test failjob get_options()"""
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
        args = run_get_options(['testjob1', 'job2'])
        self.assertEqual(args.jobnames, ['testjob1', 'job2'])
        self.assertEqual(args.force, False)
        self.assertEqual(args.email, True)
        for arg in ['-f', '--force']:
            args = run_get_options([arg, 'testjob'])
            self.assertEqual(args.force, True)
            self.assertEqual(args.jobnames, ['testjob'])
        for arg in ['-n', '--no-email']:
            args = run_get_options([arg, 'testjob'])
            self.assertEqual(args.email, False)
            self.assertEqual(args.jobnames, ['testjob'])

    def test_fail_job(self):
        """Test failjob fail_job()"""
        class DummyJob(object):
            failed = False
            name = 'testjob'

            def admin_fail(self, email):
                self.failed = True
                self.failed_email = email

        class DummyStdin(object):
            def __init__(self, answer):
                self.answer = answer

            def readline(self):
                return self.answer

        def run_fail_job(job, force, email, answer):
            oldout = sys.stdout
            oldin = sys.stdin
            try:
                sio = StringIO()
                sys.stdout = sio
                sys.stdin = DummyStdin(answer)
                fail_job(job, force, email)
                return sio.getvalue()
            finally:
                sys.stdout = oldout
                sys.stdin = oldin
        j = DummyJob()
        out = run_fail_job(j, True, True, None)
        self.assertEqual(j.failed, True)
        self.assertEqual(j.failed_email, True)
        self.assertEqual(out, '')
        for no in ('', 'n', 'x'):
            j = DummyJob()
            out = run_fail_job(j, False, True, no)
            self.assertEqual(j.failed, False)
            self.assertEqual(out, 'Fail job testjob? ')
        for yes in ('y', 'Y', 'yes'):
            j = DummyJob()
            out = run_fail_job(j, False, False, yes)
            self.assertEqual(j.failed, True)
            self.assertEqual(j.failed_email, False)
            self.assertEqual(out, 'Fail job testjob? ')

    def test_main(self):
        """Test failjob main()"""
        class DummyJob(object):
            def __init__(self, mod):
                self.mod = mod

            def admin_fail(self, email):
                self.mod.job_failed = True
                self.mod.job_failed_email = email

        class DummyWebService(object):
            def __init__(self, mod):
                self.mod = mod

            def get_running_pid(self):
                return None

            def get_job_by_name(self, state, name):
                if state == 'COMPLETED' and name == 'testjob':
                    return DummyJob(self.mod)
                else:
                    return None

        class DummyModule(object):
            config = 'testconfig'
            job_failed = False

            def get_web_service(self, config):
                return DummyWebService(self)

        old = sys.argv
        olderr = sys.stderr
        try:
            sio = StringIO()
            sys.stderr = sio
            mod = DummyModule()
            sys.argv = ['testprogram'] + ['-f', 'badjob']
            main(mod)
            self.assertEqual(sio.getvalue(), 'Could not find job badjob\n')
            self.assertEqual(mod.job_failed, False)

            sio = StringIO()
            sys.stderr = sio
            mod = DummyModule()
            sys.argv = ['testprogram'] + ['-f', 'testjob']
            main(mod)
            self.assertEqual(sio.getvalue(), '')
            self.assertEqual(mod.job_failed, True)
        finally:
            sys.argv = old
            sys.stderr = olderr


if __name__ == '__main__':
    unittest.main()
