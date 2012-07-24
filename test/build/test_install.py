import unittest
import saliweb.build
import warnings
import re
import os
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
    def Execute(self, target):
        self.execute_target = target
    def Value(self, contents):
        pass


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

    def test_install_directories(self):
        """Check _install_directories function"""
        class DummyConfig:
            directories = {'install':'testinst', 'INCOMING':'testinc',
                           'test':'foo'}
            backend = {'user': 'testback'}
        e = DummyEnv()
        e['config'] = DummyConfig()
        e['service_name'] = 'testser'
        saliweb.build._install_directories(e)
        self.assertEqual(len(e.command_target), 3)
        self.assertEqual(e.command_target[0][0], 'foo')
        self.assertEqual(e.command_target[1][0], 'testinc')
        self.assertEqual(e.command_target[2][0], 'testinst/README')

    def test_install_config(self):
        """Check _install_config function"""
        class DummyConfig:
            database = {'backend_config': 'backend.conf',
                        'frontend_config' : 'frontend.conf'}
        class DummyNode:
            path = 'test.conf'
        e = DummyEnv()
        e['config'] = DummyConfig()
        e['confdir'] = 'testcfg'
        e['configfile'] = DummyNode()
        saliweb.build._install_config(e)
        self.assertEqual(e['instconfigfile'], 'testcfg/test.conf')
        self.assertEqual(e.install_target, 'testcfg')
        self.assertEqual(e.install_files.path, 'test.conf')
        self.assertEqual(len(e.command_target), 2)
        self.assertEqual(e.command_target[0][0], 'testcfg/backend.conf')
        self.assertEqual(e.command_target[1][0], 'testcfg/frontend.conf')

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
            e['perldir'] = 'testperl'
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

    def test_install_html(self):
        """Check _InstallHTML function"""
        def make_env():
            e = DummyEnv()
            e['htmldir'] = 'testhtml'
            return e
        e = make_env()
        saliweb.build._InstallHTML(e, ['foo', 'bar'])
        self.assertEqual(e.install_target, 'testhtml')
        self.assertEqual(e.install_files, ['foo', 'bar'])

        e = make_env()
        saliweb.build._InstallHTML(e, ['foo', 'baz'], subdir='mysub')
        self.assertEqual(e.install_target, 'testhtml/mysub')
        self.assertEqual(e.install_files, ['foo', 'baz'])

    def test_install_txt(self):
        """Check _InstallTXT function"""
        def make_env():
            e = DummyEnv()
            e['txtdir'] = 'testtxt'
            return e
        e = make_env()
        saliweb.build._InstallTXT(e, ['foo', 'bar'])
        self.assertEqual(e.install_target, 'testtxt')
        self.assertEqual(e.install_files, ['foo', 'bar'])

        e = make_env()
        saliweb.build._InstallTXT(e, ['foo', 'baz'], subdir='mysub')
        self.assertEqual(e.install_target, 'testtxt/mysub')
        self.assertEqual(e.install_files, ['foo', 'baz'])

    def test_install_cgi(self):
        """Check _InstallCGI function"""
        def make_env():
            e = DummyEnv()
            e['instconfigfile'] = 'testcfg'
            e['version'] = 'testver'
            e['service_name'] = 'testser'
            e['cgidir'] = 'testcgi'
            return e
        e = make_env()
        saliweb.build._InstallCGI(e, ['foo', 'bar'])
        self.assertEqual(len(e.command_target), 2)
        self.assertEqual(e.command_target[0][0], 'testcgi/foo')
        self.assertEqual(e.command_target[1][0], 'testcgi/bar')

        e = make_env()
        saliweb.build._InstallCGI(e, ['foo', 'bar'], subdir='mysub')
        self.assertEqual(len(e.command_target), 2)
        self.assertEqual(e.command_target[0][0], 'testcgi/mysub/foo')
        self.assertEqual(e.command_target[1][0], 'testcgi/mysub/bar')

    def test_install_perl(self):
        """Check _InstallPerl function"""
        class DummyConfig:
            frontends = {}

        def make_env():
            e = DummyEnv()
            e['instconfigfile'] = 'testcfg'
            e['version'] = 'testver'
            e['service_name'] = 'testser'
            e['perldir'] = 'testperl'
            e['config'] = DummyConfig()
            return e
        e = make_env()
        saliweb.build._InstallPerl(e, ['foo', 'bar'])
        self.assertEqual(len(e.command_target), 2)
        self.assertEqual(e.command_target[0][0], 'testperl/foo')
        self.assertEqual(e.command_target[1][0], 'testperl/bar')

        e = make_env()
        saliweb.build._InstallPerl(e, ['foo', 'bar'], subdir='mysub')
        self.assertEqual(len(e.command_target), 2)
        self.assertEqual(e.command_target[0][0], 'testperl/mysub/foo')
        self.assertEqual(e.command_target[1][0], 'testperl/mysub/bar')

    def test_subst_install(self):
        """Check _subst_install function"""
        class DummyNode(object):
            def __init__(self, contents=None, path=None):
                self.contents = contents
                self.path = path
            def get_contents(self):
                return self.contents
        open('dummysrc', 'w').write('line1\nfoo@CONFIG@bar\nline2\n')
        for ver, expver in (('None', "undef"), ('r345', "'r345'")):
            e = DummyEnv()
            saliweb.build._subst_install(e, [DummyNode(path='dummytgt')],
                                         [DummyNode(path='dummysrc'),
                                          DummyNode(contents='mycfg'),
                                          DummyNode(contents=ver),
                                          DummyNode(contents='myser'),
                                          DummyNode(contents='')])
            self.assertEqual(e.execute_target.target.path, 'dummytgt')
            self.assertEqual(e.execute_target.mode, 0755)
            f = open('dummytgt').read()
            self.assertEqual(f, "line1\nfoo'mycfg', %s, 'myser', undefbar\n"
                                "line2\n" % expver)
            os.unlink('dummytgt')
        os.unlink('dummysrc')


if __name__ == '__main__':
    unittest.main()
