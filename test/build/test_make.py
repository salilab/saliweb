import unittest
import re
import os
import saliweb.build
from io import StringIO

class MakeTest(unittest.TestCase):
    """Check make* functions"""

    def test_make_readme(self):
        """Test _make_readme() function"""
        class DummySource(object):
            def get_contents(self):
                return 'testser'
        class DummyTarget(object):
            path = 'dummytgt'

        saliweb.build._make_readme(None, [DummyTarget()], [DummySource()])
        with open('dummytgt') as fh:
            f = fh.read()
        self.assertTrue(re.match('Do not edit.*source files for the testser '
                                 'service,.*and run \'scons\' to install them',
                                 f, re.DOTALL), 'regex match failed on ' + f)
        os.unlink('dummytgt')

    def test_make_script(self):
        """Test _make_script() function"""
        class DummyEnv(object):
            def Execute(self, cmd):
                self.cmd = cmd
        for t in ('mytest.py', 'mytest'):
            class DummyTarget(object):
                path = t
                def __str__(self):
                    return self.path
            e = DummyEnv()
            saliweb.build._make_script(e, [DummyTarget()], [])
            self.assertEqual(e.cmd.target.path, t)
            self.assertEqual(e.cmd.mode, 0o700)

            with open(t) as fh:
                f = fh.read()
            self.assertTrue(re.match('#!/usr/bin/python.*'
                                     r'import saliweb\.backend\.mytest$.*'
                                     r'backend\.mytest\.main', f,
                                     re.DOTALL | re.MULTILINE),
                            'regex match failed on ' + f)
            os.unlink(t)

    def test_make_cgi_script(self):
        """Test _make_cgi_script() function"""
        class DummySource(object):
            def get_contents(self):
                return 'testser'
        class DummyEnv(object):
            def Execute(self, cmd):
                self.cmd = cmd
        for t, r in (('mytest.cgi', r'my \$m = new testser;'
                                    r'.*display_mytest_page\(\)'),
                     ('job', 'use saliweb::frontend::RESTService;'
                             '.*@testser::ISA = qw.*display_submit_page.*'
                             'display_results_page')):
            class DummyTarget(object):
                path = t
                def __str__(self):
                    return self.path
            e = DummyEnv()
            saliweb.build._make_cgi_script(e, [DummyTarget()],
                                           [DummySource(), DummySource()])
            self.assertEqual(e.cmd.target.path, t)
            self.assertEqual(e.cmd.mode, 0o755)

            with open(t) as fh:
                f = fh.read()
            self.assertTrue(re.match(r'#!/usr/bin/perl \-w.*' + r,
                                     f, re.DOTALL),
                            'regex match failed on ' + f)
            os.unlink(t)

    def test_make_web_service(self):
        """Test _make_web_service() function"""
        class DummySource(object):
            def __init__(self, contents):
                self.contents = contents
            def get_contents(self):
                return self.contents
        class DummyTarget(object):
            path = 'dummytgt'
        for ver, expver in (('None', 'version = None'),
                            ('r345', 'version = r\'r345\'')):
            saliweb.build._make_web_service(None, [DummyTarget()],
                                            [DummySource('mycfg'),
                                             DummySource('mymodname'),
                                             DummySource('mypydir'),
                                             DummySource(ver)])
            with open('dummytgt') as fh:
                f = fh.read()
            self.assertTrue(re.match(
                "config = 'mycfg'.*pydir = 'mypydir'.*"
                r"import mymodname\.backend as.*"
                r"import mymodname as.*ws = backend\.get_web.*"
                r"ws\.%s" % expver, f, re.DOTALL),
                'regex match failed on ' + f)
            os.unlink('dummytgt')


if __name__ == '__main__':
    unittest.main()
