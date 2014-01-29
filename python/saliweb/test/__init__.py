"""Utility classes and functions to aid in testing Sali lab web services."""

import unittest
import os
import shutil
import tempfile
import saliweb.backend


class RunInDir(object):
    """Change to the given directory, and change back when the object
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
    """Make a temporary directory that is deleted when the object is."""

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
    """Custom TestCase subclass for testing Sali web services"""

    def make_test_job(self, jobcls, state):
        """Make a test job of the given class in the given state
           (e.g. RUNNING, POSTPROCESSING)"""
        t = TempDir()
        s = saliweb.backend._JobState(state)
        db = _DummyDB()
        db.config = _DummyConfig()
        db.config.admin_email = 'test_admin@example.com'
        metadata = {'directory': t.tmpdir, 'name': 'testjob',
                    'url': 'http://server/test/path/testjob?passwd=abc'}
        j = jobcls(db, metadata, s)
        # Make sure the directory is deleted when the job is, and not before
        j._tmpdir = t
        return j
