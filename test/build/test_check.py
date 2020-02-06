import unittest
import saliweb.build
import sys
import os
import pwd
import grp
import io
import re
import shutil
import testutil

class MockEnvFunctions(object):
    class DummyFunc(object):
        def __init__(self, name):
            self.name = name
        def __call__(self, env):
            env.append(self.name)

    def __init__(self, module, funcs):
        self._module = module
        self._funcs = funcs
        self._old = []
        for f in funcs:
            self._old.append(getattr(module, f))
        for f in funcs:
            setattr(module, f, self.DummyFunc(f))

    def __del__(self):
        for f, o in zip(self._funcs, self._old):
            setattr(self._module, f, o)


def run_catch_stderr(method, *args, **keys):
    """Run a method and return both its own return value and stderr."""
    sio = io.StringIO() if sys.version_info[0] >= 3 else io.BytesIO()
    oldstderr = sys.stderr
    try:
        sys.stderr = sio
        ret = method(*args, **keys)
        return ret, sio.getvalue()
    finally:
        sys.stderr = oldstderr

class DummyConfig: pass
class DummyEnv(dict):
    exitval = None
    def __init__(self, user):
        dict.__init__(self)
        self['configfile'] = 'test.conf'
        self['config'] = c = DummyConfig()
        c.backend = {'user': user}
    def Exit(self, val): self.exitval = val


class CheckTest(unittest.TestCase):
    """Check check functions"""

    def test_check_filesystem_sanity(self):
        """Check _check_filesystem_sanity function"""
        class DummyBackend:
            class Database:
                def __init__(self, jobcls): pass
            class WebService:
                def __init__(self, config, db): pass
                def _filesystem_sanity_check(self): pass
            class Job: pass
        e = {'config': None}
        oldbackend = saliweb.build.saliweb.backend
        try:
            saliweb.build.saliweb.backend = DummyBackend
            saliweb.build._check_filesystem_sanity(e)
        finally:
            saliweb.build.saliweb.backend = oldbackend

    def test_install_check(self):
        """Check _install_check function"""
        e = []
        m = MockEnvFunctions(saliweb.build,
                             ('_check_frontend_import', '_check_python_import',
                              '_check_filesystem_sanity'))
        saliweb.build._install_check(None, None, e)
        self.assertEqual(e, ['_check_frontend_import', '_check_python_import',
                             '_check_filesystem_sanity'])

    def test_check_directories(self):
        """Check _check_directories function"""
        e = []
        m = MockEnvFunctions(saliweb.build,
                             ('_check_directory_locations',
                              '_check_directory_permissions',
                              '_check_incoming_directory_permissions'))
        saliweb.build._check_directories(e)
        self.assertEqual(e, ['_check_directory_locations',
                             '_check_directory_permissions',
                             '_check_incoming_directory_permissions'])

    def test_check(self):
        """Check _check function"""
        class DummyEnv(list):
            def Exit(self, exitval):
                self.exitval = exitval
                raise SystemExit(exitval)
        import SCons.Script
        m = MockEnvFunctions(saliweb.build,
                             ('_check_user', '_check_ownership',
                              '_check_permissions', '_check_directories',
                              '_check_mysql', '_check_service'))

        # 'scons test' should skip checks
        SCons.Script.COMMAND_LINE_TARGETS = ['test']
        e = []
        saliweb.build._check(e)
        self.assertEqual(e, [])

        # Check missing MySQLdb dependency
        saliweb.build.MySQLdb = ImportError('foo')
        SCons.Script.COMMAND_LINE_TARGETS = []
        e = DummyEnv()
        self.assertRaises(SystemExit, saliweb.build._check, e)
        self.assertEqual(e.exitval, 1)
        self.assertEqual(e, ['_check_user', '_check_ownership',
                              '_check_permissions', '_check_directories'])

        # Normal operation
        saliweb.build.MySQLdb = None
        SCons.Script.COMMAND_LINE_TARGETS = []
        e = []
        saliweb.build._check(e)
        self.assertEqual(e, ['_check_user', '_check_ownership',
                              '_check_permissions', '_check_directories',
                              '_check_mysql', '_check_service'])

    def test_check_user(self):
        """Check _check_user function"""
        uid = os.getuid()
        # Should be OK if current user = backend user
        env = DummyEnv(pwd.getpwuid(uid).pw_name)
        saliweb.build.backend_uid_range = [uid, uid]
        ret, stderr = run_catch_stderr(saliweb.build._check_user, env)
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, None)
        self.assertEqual(stderr, '')

        # Not OK if UID is not in correct range
        env = DummyEnv(pwd.getpwuid(uid).pw_name)
        saliweb.build.backend_uid_range = [uid + 10, uid + 20]
        ret, stderr = run_catch_stderr(saliweb.build._check_user, env)
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, 1)
        self.assertTrue(re.match('\nThe backend user.*invalid user ID \(%d\).*'
                                 'between %d and %d' % (uid, uid+10, uid+20),
                                 stderr, re.DOTALL),
                                 'regex match failed on ' + stderr)

        # Not OK if current user != backend user
        env = DummyEnv('bin')  # bin user exists but hopefully is not us!
        ret, stderr = run_catch_stderr(saliweb.build._check_user, env)
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, 1)
        self.assertTrue(re.match(
                              '\nscons must be run as the backend user, which '
                              'is \'bin\'.*config file, test\.conf.*'
                              'Please run again.*sudo -u bin scons"\n',
                              stderr, re.DOTALL),
                              'regex match failed on ' + stderr)

        # Not OK if backend user does not exist
        env = DummyEnv('#baduser')
        ret, stderr = run_catch_stderr(saliweb.build._check_user, env)
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, 1)
        self.assertTrue(re.match(
                              '\nThe backend user is \'#baduser\' according.*'
                              'config file, test\.conf.*user does not exist.*'
                              'Please check.*ask a\nsysadmin.*sudo\' access',
                              stderr, re.DOTALL),
                        'regex match failed on ' + stderr)

    def test_check_sql_username_length(self):
        """Check _check_sql_username_length function"""
        # Names up to 16 characters are OK"
        for name in ('short', 'ok', "1234567890123456"):
            auth = {'user':name}
            env = DummyEnv('foo')
            saliweb.build._check_sql_username_length(env, auth, "back")
            self.assertEqual(env.exitval, None)
        # Longer names are not
        auth = {'user':'12345678901234567'}
        env = DummyEnv('foo')
        ret, stderr = run_catch_stderr(saliweb.build._check_sql_username_length,
                                       env, auth, 'mytest')
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, 1)
        self.assertTrue(re.match('\n\*\* The database username for the '
                                 'mytestend user is too long',
                                 stderr, re.DOTALL),
                        'regex match failed on ' + stderr)

    def test_check_ownership(self):
        """Check _check_ownership function"""
        dir_owner = pwd.getpwuid(os.stat('.').st_uid).pw_name
        # Not OK if directory owner == backend
        env = DummyEnv(dir_owner)
        ret, stderr = run_catch_stderr(saliweb.build._check_ownership, env)
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, 1)
        self.assertTrue(re.match('\nThe directory.*also the backend user.*'
                                 'please maintain these files.*regular user',
                                 stderr, re.DOTALL),
                        'regex match failed on ' + stderr)

        # OK if directory owner != backend
        env = DummyEnv('bin')
        ret, stderr = run_catch_stderr(saliweb.build._check_ownership, env)
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, None)
        self.assertEqual(stderr, '')

    @testutil.run_in_tempdir
    def test_check_permissions(self):
        """Check _check_permissions function"""
        conf = 'test.conf'
        with open(conf, 'w') as fh:
            fh.write('test')
        os.chmod(conf, 0o600)
        os.mkdir('.scons')
        def make_env():
            env = DummyEnv('testuser')
            env['config'].database = {'frontend_config': conf,
                                      'backend_config': conf}
            return env

        # Group- or world-readable config files should cause an error
        for perm in (0o640, 0o604):
            env = make_env()
            os.chmod(conf, perm)
            ret, stderr = run_catch_stderr(saliweb.build._check_permissions,
                                           env)
            self.assertEqual(ret, None)
            self.assertEqual(env.exitval, 1)
            self.assertTrue(re.search('The database configuration file '
                                      'test\.conf.*readable or writable.*'
                                      'To fix this.*chmod 0600 test\.conf',
                                      stderr, re.DOTALL),
                            'regex match failed on ' + stderr)
        os.chmod(conf, 0o600)

        # Everything should work OK here
        env = make_env()
        ret, stderr = run_catch_stderr(saliweb.build._check_permissions, env)
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, None)
        self.assertEqual(stderr, '')

        # If .scons is not writable, a warning should be printed
        env = make_env()
        os.chmod('.scons', 0o555)
        ret, stderr = run_catch_stderr(saliweb.build._check_permissions, env)
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, 1)
        self.assertTrue(re.search('Cannot write to \.scons directory:.*'
                                  'Permission denied.*The backend user needs '
                                  'to be able to write.*To fix this problem.*'
                                  'setfacl -m u:testuser:rwx \.scons', stderr,
                                  re.DOTALL), 'regex match failed on ' + stderr)
        os.chmod('.scons', 0o755)

        # If config files are not readable, warnings should be printed
        env = make_env()
        os.chmod(conf, 0o200)
        ret, stderr = run_catch_stderr(saliweb.build._check_permissions, env)
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, 1)
        self.assertTrue(re.match('\n\*\* Cannot read database configuration '
                                 'file:.*Permission denied.*The backend user '
                                 'needs to be able to read.*'
                                 'To fix this problem.*'
                                 'setfacl -m u:testuser:r test.conf', stderr,
                                 re.DOTALL), 'regex match failed on ' + stderr)
        os.chmod(conf, 0o600)

        # If config files are under SVN control, warnings should be printed
        env = make_env()
        os.mkdir('.svn')
        os.mkdir('.svn/text-base')
        with open('.svn/text-base/test.conf.svn-base', 'w') as fh:
            pass
        ret, stderr = run_catch_stderr(saliweb.build._check_permissions, env)
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, 1)
        self.assertTrue(re.search('The database configuration file test\.conf '
                                  'appears to be under SVN.*To fix this.*'
                                  'svn rm test\.conf; svn ci test\.conf.*'
                                  'Then recreate test\.conf using a '
                                  'fresh password', stderr, re.DOTALL),
                        'regex match failed on ' + stderr)
        shutil.rmtree('.svn', ignore_errors=True)

    def test_check_directory_locations(self):
        """Check _check_directory_locations function"""
        def make_env(install, incoming, running):
            env = DummyEnv('testuser')
            env['config'].directories = {'install': install,
                                         'INCOMING': incoming,
                                         'RUNNING': running}
            return env

        # Incoming/install on local disk, running on cluster disk is OK
        for disk in ('/var', '/usr', '/home', '/modbase1', '/modbase2',
                     '/modbase3', '/modbase4', '/modbase5'):
            for cluster in ('/wynton/home/ok',):
                env = make_env(disk, disk, cluster)
                ret, stderr = run_catch_stderr(
                               saliweb.build._check_directory_locations, env)
                self.assertEqual(ret, None)
                self.assertEqual(env.exitval, None)
                self.assertEqual(stderr, '')

        # Incoming/install on a network disk is NOT OK
        for disk in ('/guitar1', '/wynton', '/salilab'):
            env1 = make_env('/var', disk, '/wynton/ok')
            env2 = make_env(disk, '/var', '/wynton/ok')
            for (name, env) in (('INCOMING', env1), ('install', env2)):
                ret, stderr = run_catch_stderr(
                               saliweb.build._check_directory_locations, env)
                self.assertEqual(ret, None)
                self.assertEqual(env.exitval, 1)
                self.assertEqual(stderr, '\n** The ' + name + \
                                 ' directory is set to ' + disk + \
                                 '.\n** It must be on a local disk '
                                 '(e.g. /modbase1).\n\n')

        # Running on a non-Wynton disk is NOT OK
        for disk in ('/var', '/usr', '/home', '/modbase1', '/modbase2',
                     '/modbase3', '/modbase4', '/modbase5', '/guitar1',
                     '/salilab'):
            env = make_env('/modbase1', '/modbase1', disk)
            ret, stderr = run_catch_stderr(
                               saliweb.build._check_directory_locations, env)
            self.assertEqual(ret, None)
            self.assertEqual(env.exitval, 1)
            self.assertEqual(stderr, '\n** The RUNNING directory is set to ' \
                             + disk + \
                             '.\n** It must be on a cluster-accessible disk '
                             '(i.e. /wynton).\n\n')

    @testutil.run_in_tempdir
    def test_check_directory_permissions(self):
        """Check _check_directory_permissions function"""
        def make_env(dir):
            env = DummyEnv(pwd.getpwuid(os.getuid()).pw_name)
            env['config'].directories = {'testdir': dir}
            return env

        # Backend does not own this directory
        env = make_env('/')
        ret, stderr = run_catch_stderr(
                           saliweb.build._check_directory_permissions, env)
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, 1)
        self.assertTrue(re.search('Install directory / is not owned by the '
                                  'backend user', stderr, re.DOTALL),
                        'regex match failed on ' + stderr)

        # Backend *does* own this directory
        os.mkdir('test')
        os.chmod('test', 0o755)

        env = make_env('test')
        ret, stderr = run_catch_stderr(
                           saliweb.build._check_directory_permissions, env)
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, None)
        self.assertEqual(stderr, '')

        # Group- or world-writable directories should cause an error
        for perm in (0o775, 0o757):
            os.chmod('test', perm)
            env = make_env('test')
            ret, stderr = run_catch_stderr(
                           saliweb.build._check_directory_permissions, env)
            self.assertEqual(ret, None)
            self.assertEqual(env.exitval, 1)
            self.assertTrue(re.search('Install directory test appears to be '
                                      'group\- or world\-writable.*fix this.*'
                                      'chmod 755 test', stderr, re.DOTALL),
                            'regex match failed on ' + stderr)

    @testutil.run_in_tempdir
    def test_check_incoming_directory_permissions(self):
        """Check _check_incoming_directory_permissions function"""
        def make_env(dir):
            env = DummyEnv(pwd.getpwuid(os.getuid()).pw_name)
            env['config'].directories = {'INCOMING': dir}
            return env

        # Test should pass if the directory doesn't exist yet
        env = make_env('/not/exist')
        ret, stderr = run_catch_stderr(
                      saliweb.build._check_incoming_directory_permissions, env)
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, None)
        self.assertEqual(stderr, '')

        # Test should fail if the directory doesn't have correct ACLs
        os.mkdir('test')
        os.chmod('test', 0o755)

        env = make_env('test')
        ret, stderr = run_catch_stderr(
                      saliweb.build._check_incoming_directory_permissions, env)
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, 1)
        self.assertTrue(re.search('Wrong permissions on incoming directory.*'
                                  'rerun scons to recreate it.*'
                                  'Expected permissions.*Actual permissions',
                                  stderr, re.DOTALL),
                        'regex match failed on ' + stderr)

        # Test should pass if the ACLs are correct
        env = make_env('test')
        old_frontend_user = saliweb.build.frontend_user
        # 'apache' user not present on all systems; use 'nobody' instead
        try:
            saliweb.build.frontend_user = 'nobody'
            os.system('setfacl -d -m u:nobody:rwx test')
            os.system('setfacl -d -m u:%s:rwx test' \
                      % pwd.getpwuid(os.getuid()).pw_name)
            os.system('setfacl -m u:nobody:rwx test')
            saliweb.build.backend_group = \
                  grp.getgrgid(pwd.getpwuid(os.getuid()).pw_gid).gr_name
            ret, stderr = run_catch_stderr(
                      saliweb.build._check_incoming_directory_permissions, env)
            self.assertEqual(stderr, '')
            self.assertEqual(ret, None)
            self.assertEqual(env.exitval, None)
        finally:
            saliweb.build.frontend_user = old_frontend_user

    def test_generate_admin_mysql_script(self):
        """Test _generate_admin_mysql_script function"""
        frontend = {'user': 'frontuser', 'passwd': 'frontpwd'}
        backend = {'user': 'backuser', 'passwd': 'backpwd'}
        o = saliweb.build._generate_admin_mysql_script('testdb', backend,
                                                       frontend)
        self.assertEqual(os.stat(o).st_mode, 0o100600)
        with open(o) as fh:
            contents = fh.read()
        self.assertEqual(contents, \
"""CREATE DATABASE testdb;
GRANT DELETE,CREATE,DROP,INDEX,INSERT,SELECT,UPDATE ON testdb.* TO 'backuser'@'localhost' IDENTIFIED BY 'backpwd';
CREATE TABLE testdb.jobs (name VARCHAR(40) PRIMARY KEY NOT NULL DEFAULT '', user VARCHAR(40), passwd CHAR(10), contact_email VARCHAR(100), directory TEXT, url TEXT NOT NULL, state ENUM('INCOMING','PREPROCESSING','RUNNING','POSTPROCESSING','COMPLETED','FAILED','EXPIRED','ARCHIVED','FINALIZING') NOT NULL DEFAULT 'INCOMING', submit_time DATETIME NOT NULL, preprocess_time DATETIME, run_time DATETIME, postprocess_time DATETIME, finalize_time DATETIME, end_time DATETIME, archive_time DATETIME, expire_time DATETIME, runner_id VARCHAR(200), failure TEXT);
CREATE INDEX state_index ON testdb.jobs (state);
CREATE TABLE testdb.dependencies (child VARCHAR(40) NOT NULL DEFAULT '', parent VARCHAR(40) NOT NULL DEFAULT '');
CREATE INDEX child_index ON testdb.dependencies (child);
CREATE INDEX parent_index ON testdb.dependencies (parent);
GRANT SELECT ON testdb.jobs to 'frontuser'@'localhost' identified by 'frontpwd';
GRANT INSERT (name,user,passwd,directory,contact_email,url,submit_time) ON testdb.jobs to 'frontuser'@'localhost';
GRANT SELECT,INSERT,UPDATE,DELETE ON testdb.dependencies to 'frontuser'@'localhost';
""")
        os.unlink(o)

    def test_check_mysql_schema(self):
        """Test _check_mysql_schema function"""
        class DummyConf:
            pass
        # Number of fields differs between DB and backend
        env = DummyEnv('testuser')
        dbfields = []
        conf = DummyConf()
        conf.track_hostname = True
        ret, stderr = run_catch_stderr(
                         saliweb.build._check_mysql_schema, env, conf, dbfields,
                         'jobs')
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, 1)

        conf.track_hostname = False
        ret, stderr = run_catch_stderr(
                         saliweb.build._check_mysql_schema, env, conf, dbfields,
                         'jobs')
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, 1)
        self.assertTrue(re.search(
                            "'jobs' database table schema does not match.*"
                            'it has 0 fields, while the backend has 17 '
                            'fields.*entire table schema should look like.*'
                            'name VARCHAR\(40\) PRIMARY KEY NOT NULL '
                            "DEFAULT ''", stderr, re.DOTALL),
                        'regex match failed on ' + stderr)

        # Field definition differs
        env = DummyEnv('testuser')
        dbfields = [('child', 'varchar(30)', 'NO', 'PRI', '', '')]
        ret, stderr = run_catch_stderr(
                         saliweb.build._check_mysql_schema, env, conf, dbfields,
                         'dependencies')
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, 1)
        self.assertTrue(re.search("'dependencies' database table schema does "
                                  'not match.*'
                                  'mismatch has been found in the \'child\' '
                                  'field.*'
                                  'Database schema for \'child\' field:.*'
                                  'child VARCHAR\(30\).*'
                                  'Should be modified.*'
                                  'child VARCHAR\(40\).*'
                                  'entire table schema.*'
                                  'child VARCHAR\(40\) NOT NULL '
                                  'DEFAULT \'\',.*parent VARCHAR\(40\)',
                                  stderr, re.DOTALL),
                        'regex match failed on ' + stderr)

        # Fields match between DB and backend
        env = DummyEnv('testuser')
        dbfields = [('name', 'varchar(40)', 'NO', 'PRI', '', ''),
                    ('user', 'varchar(40)', 'YES', '', None, ''),
                    ('passwd', 'char(10)', 'YES', '', None, ''),
                    ('contact_email', 'varchar(100)', 'YES', '', None, ''),
                    ('directory', 'text', 'YES', '', None, ''),
                    ('url', 'text', 'NO', '', None, ''),
                    ('state', "ENUM('INCOMING','PREPROCESSING','RUNNING',"
                              "'POSTPROCESSING','COMPLETED','FAILED',"
                              "'EXPIRED','ARCHIVED','FINALIZING')", 'NO', '',
                              'INCOMING', ''),
                    ('submit_time', 'datetime', 'NO', '', '', ''),
                    ('preprocess_time', 'datetime', 'YES', '', None, ''),
                    ('run_time', 'datetime', 'YES', '', None, ''),
                    ('postprocess_time', 'datetime', 'YES', '', None, ''),
                    ('finalize_time', 'datetime', 'YES', '', None, ''),
                    ('end_time', 'datetime', 'YES', '', None, ''),
                    ('archive_time', 'datetime', 'YES', '', None, ''),
                    ('expire_time', 'datetime', 'YES', '', None, ''),
                    ('runner_id', 'varchar(200)', 'YES', '', None, ''),
                    ('failure', 'text', 'YES', '', None, ''),
                   ]
        ret, stderr = run_catch_stderr(
                         saliweb.build._check_mysql_schema, env, conf, dbfields,
                         'jobs')
        self.assertEqual(stderr, '')
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, None)

    def test_get_sorted_grant(self):
        """Test _get_sorted_grant function"""
        self.assertEqual(saliweb.build._get_sorted_grant('test grant'),
                         'test grant')
        self.assertEqual(saliweb.build._get_sorted_grant(
                          'INSERT (foo,bar,baz)'),
                          'INSERT (bar, baz, foo)')

    def test_check_mysql_grants(self):
        """Test _check_mysql_grants function"""
        # Grant is present on all tables
        env = DummyEnv('testuser')
        grants = [("GRANT INSERT ON `testdb`.* TO 'testuser'@'localhost'",)]
        ret, stderr = run_catch_stderr(
                         saliweb.build._check_mysql_grants, env, grants,
                         'testdb', 'testuser', 'INSERT')
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, None)
        self.assertEqual(stderr, '')

        # Grant column rights should match regardless of their ordering
        grants = [("GRANT INSERT(foo,bar) ON `testdb`.* "
                   "TO 'testuser'@'localhost'",)]
        ret, stderr = run_catch_stderr(
                         saliweb.build._check_mysql_grants, env, grants,
                            'testdb', 'testuser', "INSERT(bar,foo)")
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, None)
        self.assertEqual(stderr, '')

        # Grant is present on a single table
        env = DummyEnv('testuser')
        grants = [("GRANT INSERT ON `testdb`.`job` TO 'testuser'@'localhost'",)]
        ret, stderr = run_catch_stderr(
                         saliweb.build._check_mysql_grants, env, grants,
                         'testdb', 'testuser', 'INSERT', table='job')
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, None)
        self.assertEqual(stderr, '')

        # Grant is not present
        env = DummyEnv('testuser')
        grants = [("GRANT INSERT ON `testdb`.* TO 'testuser'@'localhost'",)]
        ret, stderr = run_catch_stderr(
                         saliweb.build._check_mysql_grants, env, grants,
                         'testdb', 'testuser', 'DROP')
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, 1)
        self.assertTrue(re.search('The testuser user does not appear to have.*'
                                  'admin run the following.*'
                                  'GRANT DROP ON `testdb`.* TO '
                                  "'testuser'@'localhost'", stderr, re.DOTALL),
                        'regex match failed on ' + stderr)

if __name__ == '__main__':
    unittest.main()
