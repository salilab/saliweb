import unittest
import saliweb.build
import sys
import os
import pwd
import StringIO
import re

def run_catch_stderr(method, *args, **keys):
    """Run a method and return both its own return value and stderr."""
    sio = StringIO.StringIO()
    oldstderr = sys.stderr
    try:
        sys.stderr = sio
        ret = method(*args, **keys)
        return ret, sio.getvalue()
    finally:
        sys.stderr = oldstderr

class CheckTest(unittest.TestCase):
    """Check check functions"""

    def test_check_user(self):
        """Check _check_user function"""
        class DummyConfig: pass
        class DummyEnv(dict):
            exitval = None
            def __init__(self, user):
                dict.__init__(self)
                self['configfile'] = 'test.conf'
                self['config'] = c = DummyConfig()
                c.backend = {'user': user}
            def Exit(self, val): self.exitval = val

        # Should be OK if current user = backend user
        env = DummyEnv(pwd.getpwuid(os.getuid()).pw_name)
        ret, stderr = run_catch_stderr(saliweb.build._check_user, env)
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, None)
        self.assertEqual(stderr, '')

        # Not OK if current user != backend user
        env = DummyEnv('#baduser')
        ret, stderr = run_catch_stderr(saliweb.build._check_user, env)
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, 1)
        self.assert_(re.search('scons must be run as the backend user, which '
                               'is \'#baduser\'.*config file, test\.conf.*'
                               'Please run again.*sudo -u #baduser', stderr,
                               re.DOTALL), 'regex match failed on ' + stderr)

if __name__ == '__main__':
    unittest.main()
