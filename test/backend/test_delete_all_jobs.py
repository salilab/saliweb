import unittest
import sys
from saliweb.backend import StateFileError
from saliweb.backend.delete_all_jobs import main, check_not_running
from io import StringIO


class DummyWeb(object):
    def __init__(self, pid, err=False):
        self.pid = pid
        self.err = err
        self.delete_all_jobs_called = False

    def get_running_pid(self):
        if self.err:
            raise StateFileError("state file err")
        return self.pid

    def _delete_all_jobs(self):
        self.delete_all_jobs_called = True


class DelJobTest(unittest.TestCase):
    """Check delete_all_jobs script"""

    def test_check_not_running(self):
        """Test check_not_running function"""
        web = DummyWeb(None)
        self.assertIsNone(check_not_running(web))
        web = DummyWeb(99)
        self.assertRaises(ValueError, check_not_running, web)
        web = DummyWeb(None, err=True)
        self.assertIsNone(check_not_running(web))

    def test_main(self):
        """Test delete_all_jobs main()"""
        class DummyStdin(object):
            def __init__(self, answer):
                self.answer = answer

            def readline(self):
                return self.answer

        def run_main(mod, answer):
            oldout = sys.stdout
            oldin = sys.stdin
            try:
                sio = StringIO()
                sys.stdout = sio
                sys.stdin = DummyStdin(answer)
                main(mod)
                return sio.getvalue()
            finally:
                sys.stdout = oldout
                sys.stdin = oldin

        class DummyModule(object):
            config = 'testconfig'

            def __init__(self, web):
                self.web = web

            def get_web_service(self, config):
                return self.web

        web = DummyWeb(None)
        mod = DummyModule(web)
        out = run_main(mod, 'YES')
        self.assertIn('Are you SURE', out)
        self.assertEqual(web.delete_all_jobs_called, True)

        web = DummyWeb(None)
        mod = DummyModule(web)
        out = run_main(mod, '')
        self.assertEqual(web.delete_all_jobs_called, False)


if __name__ == '__main__':
    unittest.main()
