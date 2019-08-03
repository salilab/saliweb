"""Utility classes and functions to aid in testing Sali lab web services."""

import unittest
import os
import sys
import shutil
import tempfile
import contextlib
import saliweb.backend


def _add_unittest_methods():
    """Add more modern unittest methods to Python 2.6"""
    def assertRegexpMatches(self, text, regexp, msg=None):
        if isinstance(regexp, basestring):
            regexp = re.compile(regexp)
        self.assertTrue(regexp.search(text),
            "%s: %r not found in %r" % (msg or "Regexp didn't match",
                                        regexp.pattern, text))
    def assertIn(self, member, container, msg=None):
        return self.assertTrue(member in container,
                        msg or '%s not found in %s' % (member, container))
    def assertNotIn(self, member, container, msg=None):
        return self.assertTrue(member not in container,
                        msg or '%s unexpectedly found in %s'
                        % (member, container))
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
        if delta is not None and places is not None:
            raise TypeError("specify delta or places not both")
        if delta is not None:
            return self.assertTrue(abs(first - second) <= delta,
                msg or '%s != %s within %s delta' % (str(first), str(second),
                                                     str(delta)))
        else:
            return self.assertTrue(round(abs(first - second), places) == 0,
                msg or '%s != %s within %s places' % (str(first), str(second),
                                                      str(delta)))
        return self.assertTrue(obj is not None, msg or 'unexpectedly None')
    unittest.TestCase.assertIn = assertIn
    unittest.TestCase.assertNotIn = assertNotIn
    unittest.TestCase.assertIsInstance = assertIsInstance
    unittest.TestCase.assertLess = assertLess
    unittest.TestCase.assertGreater = assertGreater
    unittest.TestCase.assertLessEqual = assertLessEqual
    unittest.TestCase.assertGreaterEqual = assertGreaterEqual
    unittest.TestCase.assertIsNone = assertIsNone
    unittest.TestCase.assertIsNotNone = assertIsNotNone
    unittest.TestCase.assertRegexpMatches = assertRegexpMatches
    unittest.TestCase.assertAlmostEqual = assertAlmostEqual


# If we're using Python 2.6, add in more modern unittest convenience
# methods
if not hasattr(unittest.TestCase, 'assertIn'):
    _add_unittest_methods()


class RunInDir(object):
    """Change to the given directory, and change back when this object
       goes out of scope."""

    def __init__(self, dir):
        try:
            self.origdir = os.getcwd()
        # Current directory might not be defined
        except OSError:
            pass
        os.chdir(dir)

    def __del__(self):
        if hasattr(self, 'origdir'):
            os.chdir(self.origdir)


class TempDir(object):
    """Make a temporary directory that is deleted when this object is."""

    def __init__(self):
        self.tmpdir = tempfile.mkdtemp()

    def __del__(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)


def RunInTempDir():
    """Run in an automatically-created temporary directory. When the
       returned object goes out of scope, the directory is deleted and the
       current directory is reset."""
    t = TempDir()
    d = RunInDir(t.tmpdir)
    d._tmpdir = t # Make sure that directory is deleted at the right time
    return d


class _DummyConfig(object):
    pass

class _DummyDB(object):

    def _update_job(self, metadata, state):
        pass


class TestCase(unittest.TestCase):
    """Custom TestCase subclass for testing Sali web service backends"""

    def make_test_job(self, jobcls, state):
        """Make a test job of the given class in the given state
           (e.g. RUNNING, POSTPROCESSING) and return the new object.
           A temporary directory is created for the job to use
           (as Job.directory) and will be deleted automatically once
           the object is destroyed."""
        t = TempDir()
        s = saliweb.backend._JobState(state)
        db = _DummyDB()
        db.config = _DummyConfig()
        db.config.admin_email = 'test_admin@example.com'
        db.config.service_name = 'test service'
        metadata = {'directory': t.tmpdir, 'name': 'testjob',
                    'url': 'http://server/test/path/testjob?passwd=abc'}
        j = jobcls(db, metadata, s)
        # Make sure the directory is deleted when the job is, and not before
        j._tmpdir = t
        return j

    def get_test_directory(self):
        """Get the full path to the directory containing test scripts.
           This can be useful for getting supplemental files needed by tests,
           which can be stored in a subdirectory of the test directory."""
        return os.environ['SALIWEB_TESTDIR']


def import_mocked_frontend(pkgname, test_file, topdir):
    """Import the named frontend module (e.g. 'modloop'), and return it.
       This sets up the environment with mocked configuration so that the
       module can be tested without being installed and without a live
       database. For this to work properly, it should be called *before*
       importing `saliweb.frontend`.

       :param str pkgname: The name of the web service frontend Python
              module to import.
       :param str test_file: File name of the test file (usually `__file__`).
       :param str topdir: Relative path from the test file to the top-level
              Python directory, i.e. that from which 'import pkgname' will
              work.
    """
    if pkgname in sys.modules:
        return sys.modules[pkgname]

    # Add search path to import pkgname
    pth = os.path.abspath(os.path.join(os.path.dirname(test_file), topdir))
    if sys.path[0] != pth:
        sys.path.insert(0, pth)

    # Provide a mock MySQL module for access to the database
    sys.path.insert(0, os.path.dirname(__file__))
    import MySQLdb
    mock_db = MySQLdb.connect()
    def mock_get_db():
        return mock_db

    import saliweb.frontend
    import saliweb.frontend.config
    saliweb.frontend.get_db = mock_get_db

    saliweb.frontend.config.DEBUG = True
    saliweb.frontend.config.TESTING = True
    saliweb.frontend.config.MODELLER_LICENSE_KEY = get_modeller_key()
    t = TempDir()
    config = os.path.join(t.tmpdir, 'test.conf')
    with open(config, 'w') as fh:
        fh.write("""
[general]
service_name: TestService
socket: /not/exist

[database]
frontend_config: frontend.conf
""")
    with open(os.path.join(t.tmpdir, 'frontend.conf'), 'w') as fh:
        fh.write("""
[frontend_db]
user: test_user_fe
passwd: test_pwd_fe
""")

    envpre = pkgname.upper()
    os.environ[envpre + "_CONFIG"] = config
    os.environ[envpre + "_VERSION"] = 'testver'

    m = sys.modules[pkgname] = __import__(pkgname)
    return m


class MockJob(object):
    """A temporary job for testing web service results pages.
       Create by calling :func:`make_frontend_job`.
    """
    #: Job name
    name = None

    #: Temporary directory containing result files (see :meth:`make_file`)
    directory = None

    #: Password needed to construct URLs for this job
    passwd = None

    def __init__(self, name, directory):
        self.name, self.directory = name, directory
        self.passwd = 'pwgoodcrypt'

    def make_file(self, name, contents=""):
        """Make a file in the job's directory with the given contents"""
        with open(os.path.join(self.directory, name), 'w') as fh:
            fh.write(contents)


@contextlib.contextmanager
def make_frontend_job(name):
    """Context manager to make a temporary job. See :class:`MockJob`.
       This can be used to test the job results page and the
       download of results files."""
    import saliweb.frontend
    tmpdir = tempfile.mkdtemp()
    j = MockJob(name, tmpdir)
    db = saliweb.frontend.get_db()
    db._jobs.append(j)
    yield j
    db._jobs.remove(j)
    shutil.rmtree(tmpdir, ignore_errors=True)


def get_modeller_key():
    """Get a valid mock Modeller key for testing"""
    return "MockModellerKey"
