import unittest
import sys
import re
import os
import saliweb.build
import tempfile
import shutil

class DummyEnv(object):
    def __init__(self, exit_val):
        self.exit_val = exit_val
        self.env = {'ENV': {}, 'service_module': 'testser'}
    def __getitem__(self, key):
        return self.env[key]
    def get(self, key, default):
        return self.env.get(key, default)
    def Clone(self):
        return self
    def Execute(self, exe):
        self.exec_str = exe
        return self.exit_val


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
        regex = '.*python .*/run\-tests\.py testser foo\.py bar\.py$'
        m = re.match(regex, e.exec_str)
        self.assertNotEqual(m, None, 'String %s does not match regex %s' \
                            % (e.exec_str, regex))
        self.assertEqual(t, 1)

        e = DummyEnv(0)
        e.env['coverage'] = 'True'
        t = saliweb.build.builder_python_tests('dummytgt',
                                               ['foo.py', 'bar.py'], e)
        regex = '.*python .*/run\-tests\.py --coverage testser ' \
                  + 'foo\.py bar\.py$'
        m = re.match(regex, e.exec_str)
        self.assertNotEqual(m, None, 'String %s does not match regex %s' \
                            % (e.exec_str, regex))

        e = DummyEnv(0)
        e.env['html_coverage'] = 'testcov'
        t = saliweb.build.builder_python_tests('dummytgt',
                                               ['foo.py', 'bar.py'], e)
        regex = '.*python .*/run\-tests\.py --html_coverage=testcov testser ' \
                  + 'foo\.py bar\.py$'
        m = re.match(regex, e.exec_str)
        self.assertNotEqual(m, None, 'String %s does not match regex %s' \
                            % (e.exec_str, regex))

    def test_fixup_perl(self):
        """Test _fixup_perl_html_coverage function"""
        tmpdir = tempfile.mkdtemp()
        with open(os.path.join(tmpdir, 'coverage.html'), 'w') as f:
            f.write('foobar')
        saliweb.build._fixup_perl_html_coverage(tmpdir)

        with open(os.path.join(tmpdir, 'index.html')) as f:
            self.assertEqual(f.read(), 'foobar')
        os.unlink(os.path.join(tmpdir, 'index.html'))
        os.rmdir(tmpdir)

    def test_builder_perl_tests(self):
        """Test builder_perl_tests function"""
        class DummyConfig:
            frontends = []
        shutil.rmtree('lib', ignore_errors=True)
        os.mkdir('lib')
        open('lib/testser.pm', 'w').write('line1\n"##CONFIG##"\nline2\n')
        open('lib/other.pm', 'w')
        e = DummyEnv(0)
        e.env['config'] = DummyConfig()
        t = saliweb.build.builder_perl_tests('dummytgt',
                                             ['foo.pl', 'bar.pl'], e)
        self.assertEqual(t, None)

        e = DummyEnv(1)
        e.env['config'] = DummyConfig()
        t = saliweb.build.builder_perl_tests('dummytgt',
                                             ['foo.pl', 'bar.pl'], e)
        self.assert_('PERL5LIB' in e.env['ENV'])
        self.assertEqual(e.exec_str, "prove foo.pl bar.pl")
        self.assertEqual(t, 1)

        e = DummyEnv(0)
        e.env['config'] = DummyConfig()
        e.env['html_coverage'] = 'testcov'
        old = saliweb.build._fixup_perl_html_coverage
        try:
            def dummy_func(outdir): pass
            saliweb.build._fixup_perl_html_coverage = dummy_func
            t = saliweb.build.builder_perl_tests('dummytgt',
                                                 ['foo.pl', 'bar.pl'], e)
        finally:
            saliweb.build._fixup_perl_html_coverage = old
        self.assert_('PERL5LIB' in e.env['ENV'])
        self.assert_('HARNESS_PERL_SWITCHES' in e.env['ENV'])

        os.unlink('lib/other.pm')
        os.unlink('lib/testser.pm')
        os.rmdir('lib')

if __name__ == '__main__':
    unittest.main()
