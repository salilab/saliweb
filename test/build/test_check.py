import unittest
import saliweb.build
import sys
import os
import pwd
import StringIO
import re
import tempfile
import shutil

class RunInTempDir(object):
    """Simple RAII-style class to run a test in a temporary directory"""
    def __init__(self):
        self.origdir = os.getcwd()
        self.tmpdir = tempfile.mkdtemp()
        os.chdir(self.tmpdir)
    def __del__(self):
        os.chdir(self.origdir)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

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

class DummyConfig: pass
class DummyEnv(dict):
    exitval = None
    def __init__(self, user):
        dict.__init__(self)
        self['configfile'] = 'test.conf'
        self['config'] = c = DummyConfig()
        c.backend = {'user': user}
    def Exit(self, val): self.exitval = val


class CheckTest(unittest.TestCase):
    """Check check functions"""

    def test_check_user(self):
        """Check _check_user function"""
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

    def test_check_permissions(self):
        """Check _check_permissions function"""
        tmpdir = RunInTempDir()
        conf = 'test.conf'
        open(conf, 'w').write('test')
        os.mkdir('.scons')
        env = DummyEnv('testuser')
        env['config'].database = {'frontend_config': conf,
                                  'backend_config': conf}
        # Everything should work OK here
        ret, stderr = run_catch_stderr(saliweb.build._check_permissions, env)
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, None)
        self.assertEqual(stderr, '')

        # If .scons is not writable, a warning should be printed
        os.chmod('.scons', 0555)
        ret, stderr = run_catch_stderr(saliweb.build._check_permissions, env)
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, 1)
        self.assert_(re.search('Cannot write to \.scons directory:.*'
                               'Permission denied.*The backend user needs to '
                               'be able to write.*To fix this problem.*'
                               'setfacl -m u:testuser:rwx \.scons', stderr,
                               re.DOTALL), 'regex match failed on ' + stderr)

        # If config files are not readable, warnings should be printed
        os.chmod('.scons', 0755)
        os.chmod(conf, 0200)
        ret, stderr = run_catch_stderr(saliweb.build._check_permissions, env)
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, 1)
        self.assert_(re.match('\n\*\* Cannot read database configuration '
                              'file:.*Permission denied.*The backend user '
                              'needs to be able to read.*To fix this problem.*'
                              'setfacl -m u:testuser:r test.conf', stderr,
                              re.DOTALL), 'regex match failed on ' + stderr)

if __name__ == '__main__':
    unittest.main()
