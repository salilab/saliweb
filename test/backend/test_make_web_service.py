import unittest
import sys
import os
import tempfile
import shutil
import subprocess
import saliweb.make_web_service
from saliweb.make_web_service import MakeWebService, get_options
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

    def test_run(self):
        """Check run of make_web_service script"""
        # Find path to make_web_service.py (can't use python -m with
        # older Python)
        mp = __import__('saliweb.make_web_service', {}, {}, ['']).__file__
        if mp.endswith('.pyc'):
            mp = mp[:-1]
        p = subprocess.Popen([sys.executable, mp],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        out, err = p.communicate()
        self.assertNotEqual(p.wait(), 0)
        self.assertTrue('for a new web service' in err, msg=err)

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

    def test_get_options(self):
        """Check make_web_service get_options()"""
        def run_get_options(args):
            old = sys.argv
            oldstderr = sys.stderr
            try:
                sys.stderr = StringIO.StringIO()
                sys.argv = ['testprogram'] + args
                return get_options()
            finally:
                sys.stderr = oldstderr
                sys.argv = old
        for bad in [[], ['long', 'short', 'extra'],
                    ['long', 'UPPERCASESHORT'], ['long', 'short with spaces']]:
            self.assertRaises(SystemExit, run_get_options, bad)
        self.assertEqual(run_get_options(['long', 'short']), ['long', 'short'])

    def test_main(self):
        """Test make_web_service main()"""
        events = []
        def dummy_get_options():
            events.append('get_options')
            return ['testlong', 'testshort']
        class DummyMakeWebService(object):
            def __init__(self, servicename, short):
                events.append('MakeWebService %s %s' % (servicename, short))
            def make(self):
                events.append('make')

        oldgetopt = saliweb.make_web_service.get_options
        oldmake = saliweb.make_web_service.MakeWebService
        try:
            saliweb.make_web_service.get_options = dummy_get_options
            saliweb.make_web_service.MakeWebService = DummyMakeWebService
            saliweb.make_web_service.main()
            self.assertEqual(events,
                             ['get_options',
                              'MakeWebService testlong testshort', 'make'])
        finally:
            saliweb.make_web_service.get_options = oldgetopt
            saliweb.make_web_service.MakeWebService = oldmake


if __name__ == '__main__':
    unittest.main()
