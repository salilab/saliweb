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

if __name__ == '__main__':
    unittest.main()
