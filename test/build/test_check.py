import unittest
import saliweb.build
import sys
import os
import pwd
import StringIO
import re
import shutil
import testutil

def run_catch_stderr(method, *args, **keys):
    """Run a method and return both its own return value and stderr."""
    sio = StringIO.StringIO()
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

    def test_check_user(self):
        """Check _check_user function"""
        # Should be OK if current user = backend user
        env = DummyEnv(pwd.getpwuid(os.getuid()).pw_name)
        ret, stderr = run_catch_stderr(saliweb.build._check_user, env)
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, None)
        self.assertEqual(stderr, '')

        # Not OK if current user != backend user
        env = DummyEnv('bin')  # bin user exists but hopefully is not us!
        ret, stderr = run_catch_stderr(saliweb.build._check_user, env)
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, 1)
        self.assert_(re.match('\nscons must be run as the backend user, which '
                              'is \'bin\'.*config file, test\.conf.*'
                              'Please run again.*sudo -u bin scons"\n$',
                              stderr, re.DOTALL),
                              'regex match failed on ' + stderr)

        # Not OK if backend user does not exist
        env = DummyEnv('#baduser')
        ret, stderr = run_catch_stderr(saliweb.build._check_user, env)
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, 1)
        self.assert_(re.match('\nThe backend user is \'#baduser\' according.*'
                              'config file, test\.conf.*user does not exist.*'
                              'Please check.*ask a\nsysadmin.*sudo\' access',
                              stderr, re.DOTALL),
                     'regex match failed on ' + stderr)

    def test_check_permissions(self):
        """Check _check_permissions function"""
        tmpdir = testutil.RunInTempDir()
        conf = 'test.conf'
        open(conf, 'w').write('test')
        os.chmod(conf, 0600)
        os.mkdir('.scons')
        def make_env():
            env = DummyEnv('testuser')
            env['config'].database = {'frontend_config': conf,
                                      'backend_config': conf}
            return env

        # Group- or world-readable config files should cause an error
        for perm in (0640, 0604):
            env = make_env()
            os.chmod(conf, perm)
            ret, stderr = run_catch_stderr(saliweb.build._check_permissions,
                                           env)
            self.assertEqual(ret, None)
            self.assertEqual(env.exitval, 1)
            self.assert_(re.search('The database configuration file '
                                   'test\.conf.*readable or writable.*'
                                   'To fix this.*chmod 0600 test\.conf',
                                   stderr, re.DOTALL),
                         'regex match failed on ' + stderr)
        os.chmod(conf, 0600)

        # Everything should work OK here
        env = make_env()
        ret, stderr = run_catch_stderr(saliweb.build._check_permissions, env)
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, None)
        self.assertEqual(stderr, '')

        # If .scons is not writable, a warning should be printed
        env = make_env()
        os.chmod('.scons', 0555)
        ret, stderr = run_catch_stderr(saliweb.build._check_permissions, env)
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, 1)
        self.assert_(re.search('Cannot write to \.scons directory:.*'
                               'Permission denied.*The backend user needs to '
                               'be able to write.*To fix this problem.*'
                               'setfacl -m u:testuser:rwx \.scons', stderr,
                               re.DOTALL), 'regex match failed on ' + stderr)
        os.chmod('.scons', 0755)

        # If config files are not readable, warnings should be printed
        env = make_env()
        os.chmod(conf, 0200)
        ret, stderr = run_catch_stderr(saliweb.build._check_permissions, env)
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, 1)
        self.assert_(re.match('\n\*\* Cannot read database configuration '
                              'file:.*Permission denied.*The backend user '
                              'needs to be able to read.*To fix this problem.*'
                              'setfacl -m u:testuser:r test.conf', stderr,
                              re.DOTALL), 'regex match failed on ' + stderr)
        os.chmod(conf, 0600)

        # If config files are under SVN control, warnings should be printed
        env = make_env()
        os.mkdir('.svn')
        os.mkdir('.svn/text-base')
        open('.svn/text-base/test.conf.svn-base', 'w')
        ret, stderr = run_catch_stderr(saliweb.build._check_permissions, env)
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, 1)
        self.assert_(re.search('The database configuration file test\.conf '
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
            env = make_env(disk, disk, '/netapp/ok')
            ret, stderr = run_catch_stderr(
                               saliweb.build._check_directory_locations, env)
            self.assertEqual(ret, None)
            self.assertEqual(env.exitval, None)
            self.assertEqual(stderr, '')

        # Incoming/install on a network disk is NOT OK
        for disk in ('/guitar1', '/netapp', '/salilab'):
            env1 = make_env('/var', disk, '/netapp/ok')
            env2 = make_env(disk, '/var', '/netapp/ok')
            for (name, env) in (('INCOMING', env1), ('install', env2)):
                ret, stderr = run_catch_stderr(
                               saliweb.build._check_directory_locations, env)
                self.assertEqual(ret, None)
                self.assertEqual(env.exitval, 1)
                self.assertEqual(stderr, '\n** The ' + name + \
                                 ' directory is set to ' + disk + \
                                 '.\n** It must be on a local disk '
                                 '(e.g. /modbase1).\n\n')

        # Running on a non-netapp disk is NOT OK
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
                             '(i.e. /netapp).\n\n')

    def test_check_directory_permissions(self):
        """Check _check_directory_permissions function"""
        tmpdir = testutil.RunInTempDir()
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
        self.assert_(re.search('Install directory / is not owned by the '
                               'backend user', stderr, re.DOTALL),
                     'regex match failed on ' + stderr)

        # Backend *does* own this directory
        os.mkdir('test')
        env = make_env('test')
        ret, stderr = run_catch_stderr(
                           saliweb.build._check_directory_permissions, env)
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, None)
        self.assertEqual(stderr, '')

        # Group- or world-writable directories should cause an error
        for perm in (0775, 0757):
            os.chmod('test', perm)
            env = make_env('test')
            ret, stderr = run_catch_stderr(
                           saliweb.build._check_directory_permissions, env)
            self.assertEqual(ret, None)
            self.assertEqual(env.exitval, 1)
            self.assert_(re.search('Install directory test appears to be '
                                   'group\- or world\-writable.*fix this.*'
                                   'chmod 755 test', stderr, re.DOTALL),
                         'regex match failed on ' + stderr)

    def test_generate_admin_mysql_script(self):
        """Test _generate_admin_mysql_script function"""
        frontend = {'user': 'frontuser', 'passwd': 'frontpwd'}
        backend = {'user': 'backuser', 'passwd': 'backpwd'}
        o = saliweb.build._generate_admin_mysql_script('testdb', backend,
                                                       frontend)
        self.assertEqual(os.stat(o).st_mode, 0100600)
        contents = open(o).read()
        self.assertEquals(contents, \
"""CREATE DATABASE testdb;
GRANT DELETE,CREATE,DROP,INDEX,INSERT,SELECT,UPDATE ON testdb.* TO 'backuser'@'localhost' IDENTIFIED BY 'backpwd';
CREATE TABLE testdb.jobs (name VARCHAR(40) PRIMARY KEY NOT NULL DEFAULT '', user VARCHAR(40), passwd CHAR(10), contact_email VARCHAR(100), directory TEXT, url TEXT NOT NULL DEFAULT '', state ENUM('INCOMING','PREPROCESSING','RUNNING','POSTPROCESSING','COMPLETED','FAILED','EXPIRED','ARCHIVED') NOT NULL DEFAULT 'INCOMING', submit_time DATETIME NOT NULL DEFAULT '', preprocess_time DATETIME, run_time DATETIME, postprocess_time DATETIME, end_time DATETIME, archive_time DATETIME, expire_time DATETIME, runner_id VARCHAR(50), failure TEXT);
GRANT SELECT ON testdb.jobs to 'frontuser'@'localhost' identified by 'frontpwd';
GRANT INSERT (name,user,passwd,directory,contact_email,url,submit_time) ON testdb.jobs to 'frontuser'@'localhost';
""")
        os.unlink(o)

    def test_check_mysql_schema(self):
        """Test _check_mysql_schema function"""
        # Number of fields differs between DB and backend
        env = DummyEnv('testuser')
        dbfields = []
        ret, stderr = run_catch_stderr(
                         saliweb.build._check_mysql_schema, env, dbfields)
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, 1)
        self.assert_(re.search("'jobs' database table schema does not match.*"
                               'it has 0 fields, while the backend has 16 '
                               'fields.*entire table schema should look like.*'
                               'name VARCHAR\(40\) PRIMARY KEY NOT NULL '
                               "DEFAULT ''", stderr, re.DOTALL),
                     'regex match failed on ' + stderr)

        # Field definition differs
        env = DummyEnv('testuser')
        dbfields = [('name', 'varchar(30)', 'NO', 'PRI', '', '')]
        ret, stderr = run_catch_stderr(
                         saliweb.build._check_mysql_schema, env, dbfields)
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, 1)
        self.assert_(re.search('table schema does not match.*'
                               'mismatch has been found in the \'name\' field.*'
                               'Database schema for \'name\' field:.*'
                               'name VARCHAR\(30\).*'
                               'Should be modified.*'
                               'name VARCHAR\(40\).*'
                               'entire table schema.*'
                               'name VARCHAR\(40\) PRIMARY KEY NOT NULL '
                               'DEFAULT \'\',.*user VARCHAR\(40\)',
                               stderr, re.DOTALL),
                     'regex match failed on ' + stderr)

        # Fields match between DB and backend
        env = DummyEnv('testuser')
        dbfields = [('name', 'varchar(40)', 'NO', 'PRI', '', ''),
                    ('user', 'varchar(40)', 'YES', '', None, ''),
                    ('passwd', 'char(10)', 'YES', '', None, ''),
                    ('contact_email', 'varchar(100)', 'YES', '', None, ''),
                    ('directory', 'text', 'YES', '', None, ''),
                    ('url', 'text', 'NO', '', '', ''),
                    ('state', "ENUM('INCOMING','PREPROCESSING','RUNNING',"
                              "'POSTPROCESSING','COMPLETED','FAILED',"
                              "'EXPIRED','ARCHIVED')", 'NO', '',
                              'INCOMING', ''),
                    ('submit_time', 'datetime', 'NO', '', '', ''),
                    ('preprocess_time', 'datetime', 'YES', '', None, ''),
                    ('run_time', 'datetime', 'YES', '', None, ''),
                    ('postprocess_time', 'datetime', 'YES', '', None, ''),
                    ('end_time', 'datetime', 'YES', '', None, ''),
                    ('archive_time', 'datetime', 'YES', '', None, ''),
                    ('expire_time', 'datetime', 'YES', '', None, ''),
                    ('runner_id', 'varchar(50)', 'YES', '', None, ''),
                    ('failure', 'text', 'YES', '', None, ''),
                   ]
        ret, stderr = run_catch_stderr(
                         saliweb.build._check_mysql_schema, env, dbfields)
        self.assertEqual(ret, None)
        self.assertEqual(env.exitval, None)
        self.assertEqual(stderr, '')

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
        self.assert_(re.search('The testuser user does not appear to have.*'
                               'admin run the following.*'
                               'GRANT DROP ON `testdb`.* TO '
                               "'testuser'@'localhost'", stderr, re.DOTALL),
                     'regex match failed on ' + stderr)

if __name__ == '__main__':
    unittest.main()
