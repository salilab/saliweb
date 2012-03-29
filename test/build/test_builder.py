import unittest
import sys
import re
import os
import saliweb.build

class DummyEnv(object):
    def __init__(self, exit_val):
        self.exit_val = exit_val
        self.env = {'ENV': {}, 'service_module': 'testser'}
    def __getitem__(self, key):
        return self.env[key]
    def Clone(self):
        return self
    def Execute(self, exe):
        self.exec_str = exe
        return self.exit_val
    def get(self, key, default):
        return default


class BuilderTest(unittest.TestCase):
    """Check builder functions"""

    def test_builder_python_tests(self):
        """Test builder_python_tests function"""
        e = DummyEnv(0)
        t = saliweb.build.builder_python_tests('dummytgt',
                                               ['foo.py', 'bar.py'], e)
        self.assertEqual(t, None)

        e = DummyEnv(1)
        t = saliweb.build.builder_python_tests('dummytgt',
                                               ['foo.py', 'bar.py'], e)
        self.assertEqual(e.env['ENV'], {'PYTHONPATH': 'python'})
        regex = 'python .*/run\-tests\.py foo\.py bar\.py$'
        m = re.match(regex, e.exec_str)
        self.assertNotEqual(m, None, 'String %s does not match regex %s' \
                            % (e.exec_str, regex))
        self.assertEqual(t, 1)

    def test_builder_perl_tests(self):
        """Test builder_perl_tests function"""
        os.mkdir('lib')
        open('lib/testser.pm', 'w').write('line1\n@CONFIG@\nline2\n')
        open('lib/other.pm', 'w')
        e = DummyEnv(0)
        t = saliweb.build.builder_perl_tests('dummytgt',
                                             ['foo.pl', 'bar.pl'], e)
        self.assertEqual(t, None)

        e = DummyEnv(1)
        t = saliweb.build.builder_perl_tests('dummytgt',
                                             ['foo.pl', 'bar.pl'], e)
        self.assert_('PERL5LIB' in e.env['ENV'])
        self.assertEqual(e.exec_str, "prove foo.pl bar.pl")
        self.assertEqual(t, 1)
        os.unlink('lib/other.pm')
        os.unlink('lib/testser.pm')
        os.rmdir('lib')

if __name__ == '__main__':
    unittest.main()
