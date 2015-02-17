import unittest
import sys
import saliweb.build
import warnings
import tempfile
import shutil
import os
import re
import StringIO
from testutil import run_catch_warnings, RunInTempDir

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

class SetupTest(unittest.TestCase):
    """Check setup functions"""

    def test_add_build_variable(self):
        """Test _add_build_variable function"""
        class Vars(object):
            def __init__(self):
                self.vars = []
            def Add(self, var):
                self.vars.append(var)

        v = Vars()
        b = saliweb.build._add_build_variable(v, "foo/bar/test.conf")
        self.assertEqual(len(v.vars), 1)
        self.assertEqual(v.vars[0].key, 'build')
        self.assertEqual(v.vars[0].default, 'test')
        self.assertEqual(v.vars[0].allowed_values, ['test'])
        self.assertEqual(b, {'test': 'foo/bar/test.conf'})

        v = Vars()
        b = saliweb.build._add_build_variable(v, ["foo/bar/test.conf",
                                                  "test/live"])
        self.assertEqual(len(v.vars), 1)
        self.assertEqual(v.vars[0].key, 'build')
        self.assertEqual(v.vars[0].default, 'test')
        v.vars[0].allowed_values.sort()
        self.assertEqual(v.vars[0].allowed_values, ['live', 'test'])
        self.assertEqual(b['test'], 'foo/bar/test.conf')
        self.assertEqual(b['live'], 'test/live')

    def test_setup_service_name(self):
        """Check _setup_service_name function"""
        def check(service_name, service_module, exp_service_module):
            env = {}
            config = DummyConfig()
            config.service_name = service_name
            saliweb.build._setup_service_name(env, config, service_module)
            self.assertEqual(env['service_name'], service_name)
            self.assertEqual(env['service_module'], exp_service_module)
        check('ModFoo', None, 'modfoo')
        check('MOD FOO', None, 'mod_foo')
        check('ModFoo', 'test', 'test')
        self.assertRaises(ValueError, check, 'test', 'ModFoo', 'test')
        self.assertRaises(ValueError, check, 'test', 'mod foo', 'test')

    def test_setup_install_directories(self):
        """Check _setup_install_directories function"""
        config = DummyConfig()
        config.directories = {'install': '/foo/bar/'}
        env = {'config': config}
        saliweb.build._setup_install_directories(env)
        for key, value in (('instdir', '/foo/bar/'),
                           ('bindir', '/foo/bar/bin'),
                           ('confdir', '/foo/bar/conf'),
                           ('pythondir', '/foo/bar/python'),
                           ('htmldir', '/foo/bar/html'),
                           ('txtdir', '/foo/bar/txt'),
                           ('cgidir', '/foo/bar/cgi'),
                           ('perldir', '/foo/bar/lib')):
            self.assertEqual(env[key], value)
            del env[key]
        del env['config']
        # Make sure it didn't create any additional directory keys
        self.assertEqual(env, {})

    def test_setup_version(self):
        """Check _setup_version function"""
        class BrokenEnv(dict):
            def __init__(self, bin):
                dict.__init__(self)
                self.bin = bin
            def WhereIs(self, bin): return self.bin
        tmpdir = tempfile.mkdtemp()
        def get_broken_env_pyscript(name, script):
            tmpfile = os.path.join(tmpdir, name)
            print >> open(tmpfile, 'w'), "#!/usr/bin/python\n" + script
            os.chmod(tmpfile, 0755)
            return BrokenEnv(tmpfile)
        curdir = RunInTempDir()

        # Check with provided version number
        env = {}
        saliweb.build._setup_version(env, '1.0')
        self.assertEqual(env, {'version': '1.0'})

        # No number provided; no svnversion binary in path
        env = BrokenEnv(None)
        ret, warns = run_catch_warnings(saliweb.build._setup_version, env, None)
        self.assertEqual(len(warns), 1)
        self.assertEqual(warns[0][0].args,
                         ("Could not find 'svnversion' binary in path",))
        self.assertEqual(env, {'version': None})

        # No number provided; cannot find svnversion binary
        env = BrokenEnv('/not/exist/svnversion')
        ret, warns = run_catch_warnings(saliweb.build._setup_version, env, None)
        self.assertEqual(len(warns), 1)
        self.assertEqual(warns[0][0].args,
                         ("Could not run /not/exist/svnversion: [Errno 2] "
                          "No such file or directory",))
        self.assertEqual(env, {'version': None})

        # No number provided; svnversion binary reports 'exported'
        env = get_broken_env_pyscript('expscript', 'print "exported"')
        ret, warns = run_catch_warnings(saliweb.build._setup_version, env, None)
        self.assertEqual(len(warns), 0)
        self.assertEqual(env, {'version': None})

        # No number provided; svnversion binary returns error
        env = get_broken_env_pyscript('errscript', """
import sys
print >> sys.stderr, "error text"
print "output text"
sys.exit(1)""")
        ret, warns = run_catch_warnings(saliweb.build._setup_version, env, None)
        self.assertEqual(len(warns), 1)
        self.assert_(re.match('Could not run \S+\/errscript: returned exit '
                              'code 1, stdout output text\n, '
                              'stderr error text\n$', warns[0][0].args[0]),
                     "%s does not match re" % warns[0][0].args[0])
        self.assertEqual(env, {'version': None})

        # No number provided; svnversion binary works
        env = get_broken_env_pyscript('workscript', 'print "1024\\n2048"')
        ret, warns = run_catch_warnings(saliweb.build._setup_version, env, None)
        self.assertEqual(len(warns), 0)
        self.assertEqual(env, {'version': 'r1024'}) # Only first line used

        # git repository
        os.mkdir('.git')
        env = get_broken_env_pyscript('gitscript', """
import sys
if sys.argv[1:4] == ['rev-parse', '--abbrev-ref', 'HEAD']:
    print "master\\nfoo"
elif sys.argv[1:4] == ['rev-parse', '--short', 'HEAD']:
    print "abc123\\nbar"
else:
    raise IOError(sys.argv)
""")
        ret, warns = run_catch_warnings(saliweb.build._setup_version, env, None)
        self.assertEqual(len(warns), 0)
        self.assertEqual(env, {'version': 'master.abc123'})

        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_setup_sconsign(self):
        """Test _setup_sconsign function"""
        class DummyEnv(dict):
            def Exit(self, val): self.exitval = val
            def SConsignFile(self, file): self.file = file
        class DummyConfig:
            backend = {'user': 'testuser'}
        # Try with existing .scons directory
        env = DummyEnv()
        if not os.path.exists('.scons'):
            os.mkdir('.scons')
        saliweb.build._setup_sconsign(env)
        self.assertEqual(env.file, '.scons/sconsign.dblite')
        os.rmdir('.scons')
        # Try without .scons directory
        env = DummyEnv()
        saliweb.build._setup_sconsign(env)
        self.assertEqual(env.file, '.scons/sconsign.dblite')
        os.rmdir('.scons')
        # Try with unwritable top-level directory
        env = DummyEnv()
        env['config'] = DummyConfig()
        tmpdir = RunInTempDir()
        os.chmod('.', 0555)
        ret, stderr = run_catch_stderr(saliweb.build._setup_sconsign, env)
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, 1)
        self.assert_(re.search('Cannot make \.scons directory:.*'
                               'Permission denied.*Please first make it '
                               'manually, with a command like.*'
                               'mkdir \.scons', stderr,
                               re.DOTALL), 'regex match failed on ' + stderr)


if __name__ == '__main__':
    unittest.main()
