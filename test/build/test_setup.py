import unittest
import saliweb.build
import warnings
import tempfile
import shutil
import os
import re
from testutil import run_catch_warnings

class DummyConfig: pass

class SetupTest(unittest.TestCase):
    """Check setup functions"""

    def test_setup_service_name(self):
        """Check _setup_service_name function"""
        def check(service_name, service_module):
            env = {}
            config = DummyConfig()
            config.service_name = service_name
            saliweb.build._setup_service_name(env, config)
            self.assertEqual(env['service_name'], service_name)
            self.assertEqual(env['service_module'], service_module)
        check('ModFoo', 'modfoo')
        check('MOD FOO', 'mod_foo')

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

        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_setup_sconsign(self):
        """Test _setup_sconsign function"""
        class DummyEnv:
            def SConsignFile(self, file): self.file = file
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

if __name__ == '__main__':
    unittest.main()
