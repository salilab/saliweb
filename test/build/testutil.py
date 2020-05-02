import warnings
import tempfile
import os
import glob
import shutil
import contextlib
import unittest


# If we're using Python 2.6, 3.0, or 3.1, add in more modern unittest
# convenience methods
if not hasattr(unittest.TestCase, 'assertIsInstance'):
    def assertIn(self, member, container, msg=None):
        return self.assertTrue(member in container,
                        msg or '%s not found in %s' % (member, container))
    def assertNotIn(self, member, container, msg=None):
        return self.assertTrue(member not in container,
                        msg or '%s unexpectedly found in %s'
                        % (member, container))
    def assertIs(self, a, b, msg=None):
        return self.assertTrue(a is b, msg or '%s is not %s' % (a, b))
    def assertIsNot(self, a, b, msg=None):
        return self.assertTrue(a is not b, msg or '%s is %s' % (a, b))
    def assertIsInstance(self, obj, cls, msg=None):
        return self.assertTrue(isinstance(obj, cls),
                        msg or '%s is not an instance of %s' % (obj, cls))
    def assertLess(self, a, b, msg=None):
        return self.assertTrue(a < b, msg or '%s not less than %s' % (a, b))
    def assertGreater(self, a, b, msg=None):
        return self.assertTrue(a > b, msg or '%s not greater than %s' % (a, b))
    def assertLessEqual(self, a, b, msg=None):
        return self.assertTrue(a <= b,
                        msg or '%s not less than or equal to %s' % (a, b))
    def assertGreaterEqual(self, a, b, msg=None):
        return self.assertTrue(a >= b,
                        msg or '%s not greater than or equal to %s' % (a, b))
    def assertIsNone(self, obj, msg=None):
        return self.assertTrue(obj is None, msg or '%s is not None' % obj)
    def assertIsNotNone(self, obj, msg=None):
        return self.assertTrue(obj is not None, msg or 'unexpectedly None')
    def assertAlmostEqual(self, first, second, places=None, msg=None,
                          delta=None):
        if first == second:
            return
        if delta is not None and places is not None:
            raise TypeError("specify delta or places not both")
        diff = abs(first - second)
        if delta is not None:
            if diff <= delta:
                return
            standard_msg = ("%s != %s within %s delta (%s difference)"
                            % (first, second, delta, diff))
        else:
            if places is None:
                places = 7
            if round(diff, places) == 0:
                return
            standard_msg = ("%s != %s within %r places (%s difference)"
                            % (first, second, places, diff))
        raise self.failureException(msg or standard_msg)
    unittest.TestCase.assertIn = assertIn
    unittest.TestCase.assertNotIn = assertNotIn
    unittest.TestCase.assertIs = assertIs
    unittest.TestCase.assertIsNot = assertIsNot
    unittest.TestCase.assertIsInstance = assertIsInstance
    unittest.TestCase.assertLess = assertLess
    unittest.TestCase.assertGreater = assertGreater
    unittest.TestCase.assertLessEqual = assertLessEqual
    unittest.TestCase.assertGreaterEqual = assertGreaterEqual
    unittest.TestCase.assertIsNone = assertIsNone
    unittest.TestCase.assertIsNotNone = assertIsNotNone
    unittest.TestCase.assertAlmostEqual = assertAlmostEqual
# Provide assert(Not)Regex for Python 2 users (assertRegexMatches is
# deprecated in Python 3)
if not hasattr(unittest.TestCase, 'assertRegex'):
    assertRegex = unittest.TestCase.assertRegexpMatches
    assertNotRegex = unittest.TestCase.assertNotRegexpMatches


def run_catch_warnings(method, *args, **keys):
    """Run a method and return both its own return value and a list of any
       warnings raised."""
    warnings.simplefilter("always")
    oldwarn = warnings.showwarning
    w  = []
    def myshowwarning(*args):
        w.append(args)
    warnings.showwarning = myshowwarning

    try:
        ret = method(*args, **keys)
        return ret, w
    finally:
        warnings.showwarning = oldwarn
        warnings.resetwarnings()

class _TempDir(object):
    def __init__(self, origdir, tmpdir):
        self.origdir, self.tmpdir = origdir, tmpdir

@contextlib.contextmanager
def temp_working_dir():
    """Simple context manager to run some code in a temporary directory"""
    origdir = os.getcwd()
    tmpdir = tempfile.mkdtemp()
    os.chdir(tmpdir)
    yield _TempDir(origdir, tmpdir)
    os.chdir(origdir)
    shutil.rmtree(tmpdir, ignore_errors=True)


@contextlib.contextmanager
def temp_dir():
    """Simple context manager to make a temporary directory"""
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)

def run_in_tempdir(func):
    """Decorate a test method to run it entirely in a temporary directory"""
    def wrapper(*args, **kwargs):
        with temp_working_dir():
            func(*args, **kwargs)
    return wrapper

def get_open_files():
    """Get a list of all files currently opened by this process"""
    pid = os.getpid()
    fd = os.path.join('/proc', '%s' % pid, 'fd')
    if not os.path.exists(fd):
        raise NotImplementedError("Needs a mounted /proc filesystem")
    for f in glob.glob('%s/*' % fd):
        try:
            yield os.readlink(f)
        except OSError:
            pass
