import unittest
import sys
import os
import tempfile
import shutil
from saliweb.make_web_service import MakeWebService
import saliweb.backend
import StringIO

class RunInTempDir(object):
    """Simple RAII-style class to run a test in a temporary directory"""
    def __init__(self):
        self.origdir = os.getcwd()
        self.tmpdir = tempfile.mkdtemp()
        os.chdir(self.tmpdir)
    def __del__(self):
        os.chdir(self.origdir)
        shutil.rmtree(self.tmpdir, ignore_errors=True)


class MakeWebServiceTests(unittest.TestCase):
    """Test the make_web_service module."""

    def test_init(self):
        """Check creation of MakeWebService object"""
        m = MakeWebService('Test Service')
        self.assertEqual(m.service_name, 'Test Service')
        self.assertEqual(m.short_name, 'test_service')
        self.assertEqual(m.user, 'test_service')
        self.assertEqual(m.db, 'test_service')

        m = MakeWebService('Test Service', 'mytest')
        self.assertEqual(m.service_name, 'Test Service')
        self.assertEqual(m.short_name, 'mytest')
        self.assertEqual(m.user, 'mytest')
        self.assertEqual(m.db, 'mytest')

    def test_make_password(self):
        """Check MakeWebService._make_password method"""
        m = MakeWebService('x')
        for pwlen in (10, 20):
            pwd = m._make_password(pwlen)
            self.assertEqual(len(pwd), pwlen)

    def test_sql_username(self):
        """Check MakeWebService._make_database_name method"""
        for (short_name, typ, expected) in (
              ["short", "veryverylongtype", "short_veryverylo"],
              ["veryverylongname", "back", "veryverylongna_b"] ):
            m = MakeWebService(short_name)
            name = m._make_database_name(typ)
            self.assertEqual(name, expected)

    def test_make(self):
        """Check MakeWebService.make method"""
        d = RunInTempDir()
        m = MakeWebService('ModFoo')
        oldstderr = sys.stderr
        try:
            sys.stderr = StringIO.StringIO()
            m.make()
        finally:
            sys.stderr = oldstderr
        # check config
        config = saliweb.backend.Config('modfoo/conf/live.conf')
        for end in ('front', 'back'):
            config._read_db_auth(end)

        # Check for generated files
        for f in ('conf/live.conf', 'conf/frontend.conf', 'conf/backend.conf',
                  'lib/modfoo.pm', 'python/modfoo/__init__.py', 'txt/help.txt',
                  'txt/contact.txt', 'SConstruct', 'lib/SConscript',
                  'python/modfoo/SConscript', 'txt/SConscript',
                  'test/SConscript', 'test/frontend/SConscript',
                  'test/backend/SConscript'):
            os.unlink('modfoo/' + f)

if __name__ == '__main__':
    unittest.main()
