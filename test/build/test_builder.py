import unittest
import sys
import re
import saliweb.build

class BuilderTest(unittest.TestCase):
    """Check builder functions"""

    def test_builder_python_tests(self):
        """Test builder_python_tests function"""
        class DummyEnv(object):
            def __init__(self, exit_val):
                self.exit_val = exit_val
                self.env = {'ENV': {}}
            def __getitem__(self, key):
                return self.env[key]
            def Clone(self):
                return self
            def Execute(self, exe):
                self.exec_str = exe
                return self.exit_val

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


if __name__ == '__main__':
    unittest.main()
