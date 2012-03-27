import unittest
import saliweb.build
import warnings
import re
from testutil import run_catch_warnings

class DummyEnv(dict):
    def Glob(self, file, ondisk):
        if 'ok' in file:
            return [file]
        else:
            return []
    def Install(self, target, files):
        self.install_target = target
        self.install_files = files
    def Command(self, *args):
        if not hasattr(self, 'command_target'):
            self.command_target = []
        self.command_target.append(args)


class InstallTest(unittest.TestCase):
    """Check install functions"""

    def test_check_perl_import(self):
        """Check to make sure check_perl_import works"""
        env = DummyEnv({'service_module': 'testmodule',
                        'perldir': '/my/test/perldir'})
        ret, warns = run_catch_warnings(saliweb.build._check_perl_import, env)
        self.assertEqual(len(warns), 1)
        self.assert_(re.search('Perl module.*\/my\/test\/perldir\/testmodule'
                               '\.pm does not.*frontend will probably not '
                               'work.*Perl module is named \'testmodule\'.*'
                               'InstallPerl.*SConscript',
                               warns[0][0].args[0], re.DOTALL),
                     'regex did not match ' + warns[0][0].args[0])

        env = DummyEnv({'service_module': 'testmodule',
                        'perldir': '/my/test/okperldir'})
        ret, warns = run_catch_warnings(saliweb.build._check_perl_import, env)
        self.assertEqual(len(warns), 0)

    def test_check_python_import(self):
        """Check to make sure check_python_import works"""
        env = DummyEnv({'service_module': 'testmodule',
                        'pythondir': '/my/test/pythondir'})
        ret, warns = run_catch_warnings(saliweb.build._check_python_import, env)
        self.assertEqual(len(warns), 1)
        self.assert_(re.search('Python module.*\/my\/test\/pythondir\/'
                               'testmodule\/__init__\.py does not.*backend '
                               'will probably not work.*Python package is '
                               'named \'testmodule\'.*'
                               'InstallPython.*SConscript',
                               warns[0][0].args[0], re.DOTALL),
                     'regex did not match ' + warns[0][0].args[0])

        env = DummyEnv({'service_module': 'testmodule',
                        'pythondir': '/my/test/okpythondir'})
        ret, warns = run_catch_warnings(saliweb.build._check_python_import, env)
        self.assertEqual(len(warns), 0)

    def test_install_admin_tools(self):
        """Check _InstallAdminTools function"""
        def make_env():
            e = DummyEnv()
            e['bindir'] = 'testbin'
            e['instconfigfile'] = 'testcfg'
            e['service_module'] = 'testser'
            e['pythondir'] = 'testpydir'
            e['version'] = 'r345'
            return e
        e = make_env()
        saliweb.build._InstallAdminTools(e)
        self.assertEqual(len(e.command_target), 5)

        e = make_env()
        saliweb.build._InstallAdminTools(e, ['myjob'])
        self.assertEqual(len(e.command_target), 2)
        self.assertEqual(e.command_target[0][0], 'testbin/myjob.py')
        self.assertEqual(e.command_target[1][0], 'testbin/webservice.py')

    def test_install_cgi_scripts(self):
        """Check _InstallCGIScripts function"""
        def make_env():
            e = DummyEnv()
            e['cgidir'] = 'testcgi'
            e['service_module'] = 'testser'
            return e
        e = make_env()
        saliweb.build._InstallCGIScripts(e)
        self.assertEqual(len(e.command_target), 7)

        e = make_env()
        saliweb.build._InstallCGIScripts(e, ['mycgi'])
        self.assertEqual(len(e.command_target), 1)
        self.assertEqual(e.command_target[0][0], 'testcgi/mycgi')

    def test_install_python(self):
        """Check _InstallPython function"""
        def make_env():
            e = DummyEnv()
            e['pythondir'] = 'testpy'
            e['service_module'] = 'testser'
            return e
        e = make_env()
        saliweb.build._InstallPython(e, ['foo', 'bar'])
        self.assertEqual(e.install_target, 'testpy/testser')
        self.assertEqual(e.install_files, ['foo', 'bar'])

        e = make_env()
        saliweb.build._InstallPython(e, ['foo', 'baz'], subdir='mysub')
        self.assertEqual(e.install_target, 'testpy/testser/mysub')
        self.assertEqual(e.install_files, ['foo', 'baz'])


if __name__ == '__main__':
    unittest.main()
