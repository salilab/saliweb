import unittest
import sys
import os
import tempfile
import shutil
import subprocess
import saliweb.make_web_service
import testutil
from saliweb.make_web_service import MakeWebService, get_options
from saliweb.make_web_service import SVNSourceControl, _run_command
from saliweb.make_web_service import GitSourceControl
import saliweb.backend
import StringIO

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
        m = MakeWebService('root', 'Test Service', git=False)
        self.assertEqual(m.service_name, 'Test Service')
        self.assertEqual(m.short_name, 'root')
        self.assertEqual(m.user, 'root')
        self.assertEqual(m.db, 'root')

    def test_make_password(self):
        """Check MakeWebService._make_password method"""
        m = MakeWebService('root', 'x', git=False)
        for pwlen in (10, 20):
            pwd = m._make_password(pwlen)
            self.assertEqual(len(pwd), pwlen)

    def test_sql_username(self):
        """Check MakeWebService._make_database_name method"""
        class Dummy(MakeWebService):
            def _get_install_dir(self):
                return "dummy"
        for (short_name, typ, expected) in (
              ["short", "veryverylongtype", "short_veryverylo"],
              ["veryverylongname", "back", "veryverylongna_b"] ):
            m = Dummy(short_name, "service name", git=False)
            name = m._make_database_name(typ)
            self.assertEqual(name, expected)

    def test_run_command(self):
        """Check _run_command"""
        _run_command('svn', ['help'], cwd='/')
        self.assertRaises(OSError, _run_command, 'svn', ['garbage'], '/')

    @testutil.run_in_tempdir
    def test_make(self):
        """Check MakeWebService.make method, using SVN"""
        class DummySourceControl(SVNSourceControl):
            def _run_svn_command(self, cmd, cwd=None):
                self.cmds.append(cmd)
        class Dummy(MakeWebService):
            def _get_install_dir(self):
                return "dummy"
        m = Dummy('modfoo', 'ModFoo', git=False)
        msc = DummySourceControl('modfoo', 'modfoo')
        m.source_control = msc
        m.user = 'root' # so that getpwnam works
        os.mkdir(m.topdir)
        msc.cmds = []
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
                  'frontend/modfoo/__init__.py', 'backend/modfoo/__init__.py',
                  'SConstruct', 'backend/modfoo/SConscript',
                  'frontend/modfoo/SConscript',
                  'frontend/modfoo/templates/SConscript',
                  'test/SConscript', 'test/frontend/SConscript',
                  'test/backend/SConscript'):
            os.unlink('modfoo/' + f)

    @testutil.run_in_tempdir
    def test_make_git(self):
        """Check MakeWebService.make method, using git"""
        class DummySourceControl(GitSourceControl):
            def _run_git_command(self, cmd, cwd=None):
                self.cmds.append(cmd)
        class Dummy(MakeWebService):
            def _get_install_dir(self):
                return "dummy"
        m = Dummy('modfoo', 'ModFoo', git=True)
        msc = DummySourceControl('modfoo', 'modfoo')
        m.source_control = msc
        m.user = 'root' # so that getpwnam works
        os.mkdir(m.topdir)
        msc.cmds = []
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
                  'frontend/modfoo/__init__.py',
                  'backend/modfoo/__init__.py',
                  'frontend/modfoo/templates/layout.html',
                  'frontend/modfoo/templates/index.html',
                  'frontend/modfoo/templates/help.html',
                  'frontend/modfoo/templates/contact.html',
                  'SConstruct', 'frontend/modfoo/SConscript',
                  'frontend/modfoo/templates/SConscript',
                  'backend/modfoo/SConscript',
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
        for bad in [[], ['--svn', 'short', 'long', 'extra'],
                    ['--svn', 'UPPERCASESHORT', 'long'],
                    ['--svn', 'short with spaces', 'long'],
                    ['short', 'long'],
                    ['--svn', '--git', 'short', 'long']]:
            self.assertRaises(SystemExit, run_get_options, bad)
        self.assertEqual(run_get_options(['--git', 'short', 'long']),
                                         (['short', 'long'], True))

    def test_main(self):
        """Test make_web_service main()"""
        events = []
        def dummy_get_options():
            events.append('get_options')
            return (['testshort', 'testlong'], False)
        class DummyMakeWebService(object):
            def __init__(self, short, servicename, git):
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
