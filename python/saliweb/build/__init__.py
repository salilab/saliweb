"""Simple SCons-based build system for web services.

   Build scripts should be run as the backend user; permissions should be set
   correctly for this user, with extra permissions added for the frontend
   user (apache), automatically by the build system.

"""

from __future__ import print_function
try:
    import MySQLdb
except ImportError as detail:
    MySQLdb = detail
import warnings
import sys
import os.path
import pwd
import saliweb.backend
import SCons.Script
from SCons.Script import File, Mkdir, Chmod, Value, Action, Builder
import subprocess
import tempfile
import re
import shutil
import glob

frontend_user = 'apache'
backend_group = None
backend_uid_range = [11800, 11900]


def _add_build_variable(vars, configs):
    if not isinstance(configs, (list, tuple)):
        configs = [configs]
    buildmap = {}
    default = None
    for c in configs:
        opt = os.path.basename(c)
        if opt.endswith('.conf'):
            opt = opt[:-5]
        if not default:
            default = opt
        buildmap[opt] = c
    vars.Add(SCons.Script.EnumVariable('build',
               "Select which web service configuration to build (e.g. to "
               "set up either a test version or the live version of the web "
               "service)""", default=default, allowed_values=buildmap.keys()))
    return buildmap


def Environment(variables, configfiles, version=None, service_module=None,
                config_class=saliweb.backend.Config):
    buildmap = _add_build_variable(variables, configfiles)
    variables.Add(SCons.Script.PathVariable('html_coverage',
                               'Directory to output HTML coverage reports into',
                               None, SCons.Script.PathVariable.PathIsDirCreate))
    variables.Add(SCons.Script.BoolVariable('coverage',
                               'Preserve output coverage files', False))
    variables.Add('python', 'Python executable to use', sys.executable)

    env = SCons.Script.Environment(variables=variables)
    # Inherit some variables from the environment:
    if 'PERL5LIB' in os.environ:
        env['ENV']['PERL5LIB'] = os.environ['PERL5LIB']
    if 'PATH' in os.environ:
        env['ENV']['PATH'] = os.environ['PATH']

    configfile = buildmap[env['build']]
    env['configfile'] = File(configfile)
    env['config'] = config = config_class(configfile)
    _setup_sconsign(env)
    _setup_version(env, version)
    _setup_service_name(env, config, service_module)
    _setup_install_directories(env)
    if not env.GetOption('clean') and not env.GetOption('help'):
        _check(env)
    _install_config(env)
    _install_directories(env)
    env.AddMethod(_InstallAdminTools, 'InstallAdminTools')
    env.AddMethod(_InstallCGIScripts, 'InstallCGIScripts')
    env.AddMethod(_InstallPython, 'InstallPython')
    env.AddMethod(_InstallHTML, 'InstallHTML')
    env.AddMethod(_InstallFrontend, 'InstallFrontend')
    env.AddMethod(_InstallPythonFrontend, 'InstallPythonFrontend')
    env.AddMethod(_InstallTXT, 'InstallTXT')
    env.AddMethod(_InstallCGI, 'InstallCGI')
    env.AddMethod(_InstallPerl, 'InstallPerl')
    env.AddMethod(_make_frontend, 'Frontend')
    env.Append(BUILDERS={'RunPerlTests': Builder(action=builder_perl_tests)})
    env.Append(BUILDERS={'RunPythonTests': \
                          Builder(action=builder_python_tests)})
    install = env.Command('install', None,
                          Action(_install_check, 'Check installation ...'))
    env.AlwaysBuild(install)
    env.Requires(install, env['config'].directories.values())
    env.Default(install)
    return env

def _fixup_perl_html_coverage(subdir):
    os.rename(os.path.join(subdir, 'coverage.html'),
              os.path.join(subdir, 'index.html'))

def _add_to_path(env, varname, val):
    if varname in env['ENV']:
        env['ENV'][varname] = val + ':' + env['ENV'][varname]
    else:
        env['ENV'][varname] = val

def builder_perl_tests(target, source, env):
    """Custom builder to run Perl tests"""
    app = "prove " + " ".join(str(s) for s in source)
    abslib = os.path.abspath('lib')
    e = env.Clone()
    _add_to_path(e, 'PERL5LIB', abslib)
    if env.get('html_coverage', None) or env.get('coverage', None):
        e['ENV']['HARNESS_PERL_SWITCHES'] = \
                     "-MDevel::Cover=+select,^lib,+ignore,."
        e.Execute('cover -delete')
    ret = e.Execute(app)
    if ret != 0:
        print("unit tests FAILED")
        return 1
    else:
        if env.get('html_coverage', None):
            outdir = os.path.join(env['html_coverage'], 'perl')
            e.Execute('cover -outputdir %s' % outdir)
            _fixup_perl_html_coverage(outdir)
            e.Execute('cover -delete')

def builder_python_tests(target, source, env):
    """Custom builder to run Python tests"""
    mod = os.path.join(os.path.dirname(saliweb.__file__), 'test',
                       'run-tests.py')
    if env.get('html_coverage', None):
        mod += ' --html_coverage=%s' % env['html_coverage']
    if env.get('coverage', None):
        mod += ' --coverage'
    mod += " " + env['service_module']
    app = env['python'] + " " + mod + " " + " ".join(str(s) for s in source)
    e = env.Clone()
    e['ENV']['PYTHONPATH'] = 'python'
    ret = e.Execute(app)
    if ret != 0:
        print("unit tests FAILED")
        return 1


def _install_check(target, source, env):
    """Check the final installation for sanity"""
    _check_perl_import(env)
    _check_python_import(env)
    _check_filesystem_sanity(env)


def _check_perl_import(env):
    """Check to make sure Perl import of modname will work"""
    modname = env['service_module']
    modfile = '%s/%s.pm' % (env['perldir'], modname)
    glob_modfile = env.Glob(modfile, ondisk=False)
    if len(glob_modfile) != 1:
        warnings.warn("The Perl module file %s does not appear to be set "
                      "up for installation. Thus, the frontend will probably "
                      "not work. Make sure that the Perl module is named '%s' "
                      "and there is an InstallPerl call somewhere in the "
                      "SConscripts to install it. " % (modfile, modname))


def _check_python_import(env):
    """Check to make sure Python import of modname will work"""
    modname = env['service_module']
    modfile = '%s/%s/__init__.py' % (env['pythondir'], modname)
    glob_modfile = env.Glob(modfile, ondisk=False)
    if len(glob_modfile) != 1:
        warnings.warn("The Python module file %s does not appear to be set "
                      "up for installation. Thus, the backend will probably "
                      "not work. Make sure that the Python package is named "
                      "'%s' and there is an InstallPython call somewhere "
                      "in the SConscripts to install it. " \
                      % (modfile, modname))


def _check_filesystem_sanity(env):
    """Check the filesystem for consistency with the job database"""
    config = env['config']
    db = saliweb.backend.Database(saliweb.backend.Job)
    ws = saliweb.backend.WebService(config, db)
    ws._filesystem_sanity_check()


def _setup_sconsign(env):
    if not os.path.exists('.scons'):
        try:
            os.mkdir('.scons')
        except OSError as detail:
            print("""
** Cannot make .scons directory: %s
** Please first make it manually, with a command like
   mkdir .scons
""" % str(detail), file=sys.stderr)
            env.Exit(1)
    env.SConsignFile('.scons/sconsign.dblite')


def _run_version_binary(env, cmd, args):
    fullcmd = env.WhereIs(cmd)
    if fullcmd:
        try:
            p = subprocess.Popen([fullcmd] + args, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
            ret = p.communicate()
            if p.returncode:
                raise OSError("returned exit code %d, stdout %s, "
                              "stderr %s" \
                              % (p.returncode, ret[0], ret[1]))
            return ret[0].split('\n')[0]
        except OSError as detail:
            warnings.warn("Could not run %s: %s" \
                          % (fullcmd, str(detail)))
    else:
        warnings.warn("Could not find '%s' binary in path" % cmd)


def _setup_version(env, version):
    if version is None:
        if os.path.exists('.git'):
            branch = _run_version_binary(env, 'git',
                                         ['rev-parse', '--abbrev-ref', 'HEAD'])
            rev = _run_version_binary(env, 'git',
                                         ['rev-parse', '--short', 'HEAD'])
            if branch and rev:
                version = branch + '.' + rev
        else:
            v = _run_version_binary(env, 'svnversion', [])
            if v and v != 'exported':
                version = 'r' + v
    env['version'] = version


def _setup_service_name(env, config, service_module):
    env['service_name'] = config.service_name
    if service_module:
        if ' ' in service_module or service_module.lower() != service_module:
            raise ValueError('service_module must be all lowercase and '
                             'contain no spaces')
        env['service_module'] = service_module
    else:
        env['service_module'] = config.service_name.lower().replace(' ', '_')


def _setup_install_directories(env):
    config = env['config']
    env['instdir'] = config.directories['install']
    env['bindir'] = os.path.join(env['instdir'], 'bin')
    env['confdir'] = os.path.join(env['instdir'], 'conf')
    env['pythondir'] = os.path.join(env['instdir'], 'python')
    env['htmldir'] = os.path.join(env['instdir'], 'html')
    env['frontenddir'] = os.path.join(env['instdir'], 'frontend')
    env['txtdir'] = os.path.join(env['instdir'], 'txt')
    env['cgidir'] = os.path.join(env['instdir'], 'cgi')
    env['perldir'] = os.path.join(env['instdir'], 'lib')


def _check(env):
    # tests run locally, so don't need the installation to work properly
    cmdtgt = SCons.Script.COMMAND_LINE_TARGETS
    if len(cmdtgt) == 1 and cmdtgt[0].startswith('test'):
        return
    _check_user(env)
    _check_ownership(env)
    _check_permissions(env)
    _check_directories(env)
    if isinstance(MySQLdb, Exception):
        print("Could not import the MySQLdb module: %s" % MySQLdb,
              file=sys.stderr)
        print("This module is needed by the backend.", file=sys.stderr)
        env.Exit(1)
    _check_mysql(env)
    _check_service(env)


def _check_directories(env):
    _check_directory_locations(env)
    _check_directory_permissions(env)
    _check_incoming_directory_permissions(env)


def _check_directory_locations(env):
    for key in ('install', 'INCOMING'):
        dir = env['config'].directories[key]
        if not dir.startswith('/modbase') and not dir.startswith('/usr') \
           and not dir.startswith('/var') and not dir.startswith('/home'):
            print("""
** The %s directory is set to %s.
** It must be on a local disk (e.g. /modbase1).
""" % (key, dir), file=sys.stderr)
            env.Exit(1)

    running = env['config'].directories['RUNNING']
    if not running.startswith('/netapp') and not running.startswith('/wynton'):
        print("""
** The RUNNING directory is set to %s.
** It must be on a cluster-accessible disk (i.e. /netapp or /wynton).
""" % running, file=sys.stderr)
        env.Exit(1)


def _check_directory_permissions(env):
    backend_user = env['config'].backend['user']
    for dir in env['config'].directories.values():
        if not os.path.exists(dir):
            continue
        out, err = subprocess.Popen(['/usr/bin/getfacl', dir],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE).communicate()
        if not re.search('^# owner: ' + backend_user, out,
                         re.MULTILINE | re.DOTALL):
            print("""
** Install directory %s is not owned by the backend user, %s!
** Please change the ownership of this directory.
""" % (dir, backend_user), file=sys.stderr)
            env.Exit(1)
        if not re.search('^group::.\-..*other::.\-.', out,
                         re.MULTILINE | re.DOTALL):
            print("""
** Install directory %s appears to be group- or world-writable!
** It should only be writable by the backend user, %s.
** To fix this, run
   /usr/bin/sudo -u %s chmod 755 %s
** or delete the directory and then rerun scons to recreate it.
""" % (dir, backend_user, backend_user, dir), file=sys.stderr)
            env.Exit(1)

def _check_incoming_directory_permissions(env):
    """Make sure that the incoming directory, if it exists, has
       correct permissions"""
    global backend_group
    backend_user = env['config'].backend['user']
    if not backend_group:
        backend_group = backend_user
    incoming = env['config'].directories['INCOMING']
    if not os.path.exists(incoming):
        return
    out, err = subprocess.Popen(['/usr/bin/getfacl', incoming],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE).communicate()
    lines = [x for x in out.split('\n')[1:] if x != '']
    expected_lines = [ '# owner: ' + backend_user,
                       '# group: ' + backend_group,
                       'user::rwx', 'user:%s:rwx' % frontend_user,
                       'group::r-x', 'mask::rwx', 'other::r-x',
                       'default:user::rwx',
                       'default:user:%s:rwx' % frontend_user,
                       'default:user:%s:rwx' % backend_user,
                       'default:group::r-x', 'default:mask::rwx',
                       'default:other::r-x' ]
    if sorted(lines) != sorted(expected_lines):
        print("""
** Wrong permissions on incoming directory %s!
** Please remove this directory, then rerun scons to recreate it with
** the correct permissions.
** Expected permissions: %s
** Actual permissions: %s
""" % (incoming, expected_lines, lines), file=sys.stderr)
        env.Exit(1)


def _check_ownership(env):
    """The backend user should *not* own the checkout directory"""
    backend_user = env['config'].backend['user']
    backend_uid = pwd.getpwnam(backend_user).pw_uid
    owner_uid = os.stat('.').st_uid
    if backend_uid == owner_uid:
        print("""
The directory containing the web service checkout is owned by the %s
user. This is also the backend user. The checkout should *not* be owned
by the backend; please maintain these files in a regular user's
account instead.
""" % (backend_user), file=sys.stderr)
        env.Exit(1)


def _check_user(env):
    backend_user = env['config'].backend['user']
    try:
        pwd.getpwnam(backend_user)
    except KeyError:
        print("""
The backend user is '%s' according to the config file, %s.
This user does not exist on the system. Please check to make sure you have
specified the name correctly in the config file, and if so, please ask a
sysadmin to set up the account for you and give you 'sudo' access to it.
""" % (backend_user, env['configfile']), file=sys.stderr)
        env.Exit(1)

    uid = os.getuid()
    current_user = pwd.getpwuid(uid).pw_name
    if backend_user != current_user:
        print("""
scons must be run as the backend user, which is '%s' according to the
config file, %s.
You are currently trying to run scons as the '%s' user.
Please run again with something like \"/usr/bin/sudo -u %s scons\"
""" % (backend_user, env['configfile'], current_user, backend_user),
               file=sys.stderr)
        env.Exit(1)

    if uid < backend_uid_range[0] or uid > backend_uid_range[1]:
        print("""
The backend user (%s) has an invalid user ID (%d); it must be
between %d and %d. Please ask a sysadmin to help you fix this problem.
""" % (backend_user, uid, backend_uid_range[0], backend_uid_range[1]),
              file=sys.stderr)
        env.Exit(1)


def _check_permissions(env):
    """Make sure we can write to the .scons directory, and read the
       database configuration files"""
    try:
        open('.scons/.test', 'w')
        os.unlink('.scons/.test')
    except IOError as detail:
        print("""
** Cannot write to .scons directory: %s
** The backend user needs to be able to write to this directory.
** To fix this problem, make sure that your checkout is on a local disk
** (e.g. /modbase1, /modbase2, etc., not /netapp) and run
   setfacl -m u:%s:rwx .scons
""" % (str(detail), env['config'].backend['user']), file=sys.stderr)
        env.Exit(1)
    for end in ('back', 'front'):
        conf = env['config'].database['%send_config' % end]
        if not os.path.exists(conf):
            continue
        out, err = subprocess.Popen(['/usr/bin/getfacl', conf],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE).communicate()
        if not re.search('^group::\-\-\-.*^other::\-\-\-', out,
                         re.MULTILINE | re.DOTALL):
            print("""
** The database configuration file %s appears to be group- or world-
** readable or writable. It should only be user readable and writable.
** To fix this, run
   chmod 0600 %s
""" % (conf, conf), file=sys.stderr)
            env.Exit(1)
        dir, base = os.path.split(conf)
        svnbase = os.path.join(dir, '.svn', 'text-base', base + '.svn-base')
        if os.path.exists(svnbase):
            print("""
** The database configuration file %s appears to be under SVN control.
** Please do not put files containing sensitive information (i.e. passwords)
** under SVN control.
** To fix this, run
   svn rm %s; svn ci %s
** Then recreate %s using a fresh password.
""" % (conf, conf, conf, conf), file=sys.stderr)
            env.Exit(1)
        try:
            open(conf)
        except IOError as detail:
            print("""
** Cannot read database configuration file: %s
** The backend user needs to be able to read this file.
** To fix this problem, make sure that your checkout is on a local disk
** (e.g. /modbase1, /modbase2, etc., not /netapp) and run
   setfacl -m u:%s:r %s
""" % (str(detail), env['config'].backend['user'], conf), file=sys.stderr)
            env.Exit(1)


def _format_shell_command(env, cmd):
    sudo_user = os.environ.get('SUDO_USER')
    if sudo_user and sudo_user != env['config'].backend['user']:
        return "/usr/bin/sudo -u %s " % env['config'].backend['user'] + cmd
    else:
        return cmd


def _check_service(env):
    config = env['config']
    db = saliweb.backend.Database(saliweb.backend.Job)
    ws = saliweb.backend.WebService(config, db)
    try:
        pid = ws.get_running_pid()
        binary = os.path.join(env['bindir'], 'service.py')
        if pid is None:
            print("** Backend daemon is not currently running. Run")
            print("   " + _format_shell_command(env, "%s start" % binary))
            print("** to have it start processing jobs.")
        else:
            print("** Backend daemon is currently running. Run")
            print("   " + _format_shell_command(env, "%s restart" % binary))
            print("** to restart it to pick up any changes.")
    except saliweb.backend.StateFileError as detail:
        print("** Backend daemon will not start due to a previous failure. ")
        print("** You will need to fix this manually before it will run again.")
        print("** Refer to %s for more information"
              % config.backend['state_file'])


def _check_mysql(env):
    """Make sure that we can connect to the database as both the frontend and
       backend users."""
    c = env['config']
    c._read_db_auth('back')
    backend = dict(c.database)
    c._read_db_auth('front')
    frontend = dict(c.database)

    try:
        db = MySQLdb.connect(db=c.database['db'], user=backend['user'],
                             unix_socket=c.database['socket'],
                             passwd=backend['passwd'])
        cur = db.cursor()
        for table in ('jobs', 'dependencies'):
            cur.execute('DESCRIBE ' + table)
            _check_mysql_schema(env, c, cur, table)
        cur.execute('SHOW GRANTS FOR CURRENT_USER')
        _check_mysql_grants(env, cur, c.database['db'], backend['user'],
                            'SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, '
                            'INDEX')

        db = MySQLdb.connect(db=c.database['db'], user=frontend['user'],
                             unix_socket=c.database['socket'],
                             passwd=frontend['passwd'])
        cur = db.cursor()
        cur.execute('SHOW GRANTS FOR CURRENT_USER')
        if c.track_hostname:
            hostname = 'hostname, '
        else:
            hostname = ''
        _check_mysql_grants(env, cur, c.database['db'], frontend['user'],
                            'SELECT, INSERT (submit_time, contact_email, url, '
                            'passwd, user, directory, %sname)' % hostname,
                            table='jobs')
        _check_mysql_grants(env, cur, c.database['db'], frontend['user'],
                            'SELECT, INSERT, UPDATE, DELETE',
                            table='dependencies')
    except (MySQLdb.OperationalError, MySQLdb.ProgrammingError) as detail:
        # Only complain about possible too-long DB usernames if MySQL
        # itself first complained
        _check_sql_username_length(env, frontend, 'front')
        _check_sql_username_length(env, backend, 'back')
        outfile = _generate_admin_mysql_script(c.database['db'], backend,
                                               frontend)
        print("""
** Could not query the jobs table in the %s database using both the
** frontend and backend users. The actual error message follows:
** %s
** This either means that you have mistyped the names or passwords of the
** frontend or backend users in the configuration file, or that the web
** service's MySQL accounts are not set up correctly. If the latter, please
** ask a sysadmin to run the commands in the file
** %s to set this up properly.
""" % (c.database['db'], str(detail), outfile), file=sys.stderr)
        env.Exit(1)

def _check_sql_username_length(env, auth, typ):
    max_length = 16 # MySQL username length limit
    username = auth['user']
    if len(username) > max_length:
        print("""
** The database username for the %send user is too long;
** MySQL usernames can be at most %d characters long.
** Please shorten the username in the configuration file.
""" % (typ, max_length), file=sys.stderr)
        env.Exit(1)

def _get_sorted_grant(grant):
    """Sort grant column rights alphabetically, so that we can match them
       reliably."""
    m = re.match('(.*?\()(.*)(\).*)$', grant)
    if m:
        fields = m.group(2).split(',')
        fields = [x.strip() for x in fields]
        fields.sort()
        return m.group(1) + ', '.join(fields) + m.group(3)
    return grant


def _check_mysql_grants(env, cursor, database, user, grant, table=None):
    if table is None:
        table = '*'
    else:
        table = '`%s`' % table
    grant = "GRANT %s ON `%s`.%s TO '%s'@'localhost'" \
            % (_get_sorted_grant(grant), database, table, user)
    for row in cursor:
        if _get_sorted_grant(row[0]) == grant:
            return
    print("""
** The %s user does not appear to have the necessary
** MySQL privileges.
** Please have an admin run the following MySQL command:
   %s
""" % (user, grant), file=sys.stderr)
    env.Exit(1)


def _generate_admin_mysql_script(database, backend, frontend):
    d = saliweb.backend.Database(None)
    fd, outfile = tempfile.mkstemp()
    commands = """CREATE DATABASE %(database)s;
GRANT DELETE,CREATE,DROP,INDEX,INSERT,SELECT,UPDATE ON %(database)s.* TO '%(backend_user)s'@'localhost' IDENTIFIED BY '%(backend_passwd)s';
CREATE TABLE %(database)s.jobs (%(schema)s);
CREATE INDEX state_index ON %(database)s.jobs (state);
CREATE TABLE %(database)s.dependencies (%(depschema)s);
CREATE INDEX child_index ON %(database)s.dependencies (child);
CREATE INDEX parent_index ON %(database)s.dependencies (parent);
GRANT SELECT ON %(database)s.jobs to '%(frontend_user)s'@'localhost' identified by '%(frontend_passwd)s';
GRANT INSERT (name,user,passwd,directory,contact_email,url,submit_time) ON %(database)s.jobs to '%(frontend_user)s'@'localhost';
GRANT SELECT,INSERT,UPDATE,DELETE ON %(database)s.dependencies to '%(frontend_user)s'@'localhost';
""" % {'database': database, 'backend_user': backend['user'],
       'backend_passwd': backend['passwd'], 'frontend_user': frontend['user'],
       'frontend_passwd': frontend['passwd'],
       'schema': ', '.join(x.get_schema() for x in d._fields),
       'depschema': ', '.join(x.get_schema() for x in d._dependfields)}
    os.write(fd, commands)
    os.close(fd)
    os.chmod(outfile, 0600)
    return outfile


def _check_mysql_schema(env, config, cursor, table):
    d = saliweb.backend.Database(None)
    if config.track_hostname:
        d.set_track_hostname()
    dbfields = []
    for row in cursor:
        dbfields.append(saliweb.backend.MySQLField(row[0], row[1].upper(),
                                                   null=row[2], key=row[3],
                                                   default=row[4]))

    fields = {'jobs': d._fields, 'dependencies': d._dependfields}[table]
    for dbfield, backfield in zip(dbfields, fields):
        dbfield.index = backfield.index # Ignore differences in indexes here
        if dbfield != backfield:
            print("""
** The '%s' database table schema does not match that expected by the backend;
** a mismatch has been found in the '%s' field. Please modify the
** table schema accordingly.
**
** Database schema for '%s' field:
   %s
** Should be modified to match the schema in the backend:
   %s
**
** For reference, the entire table schema should look like:
   %s
""" % (table, dbfield.name, dbfield.name, dbfield.get_schema(),
       backfield.get_schema(),
       ',\n   '.join(x.get_schema() for x in fields)), file=sys.stderr)
            env.Exit(1)

    if len(dbfields) != len(fields):
        print("""
** The '%s' database table schema does not match that expected by the backend;
** it has %d fields, while the backend has %d fields. Please modify the
** table schema accordingly. The entire table schema should look like:
   %s
""" % (table, len(dbfields), len(fields),
       ',\n   '.join(x.get_schema() for x in fields)), file=sys.stderr)
        env.Exit(1)


def _install_config(env):
    config = env['config']
    env['instconfigfile'] = os.path.join(env['confdir'],
                                      os.path.basename(env['configfile'].path))
    backend = config.database['backend_config']
    frontend = config.database['frontend_config']
    env.Install(env['confdir'], env['configfile'])
    # backend database info should be readable only by us
    env.Command(os.path.join(env['confdir'], os.path.basename(backend)),
                backend,
                "install -m 0400 $SOURCE $TARGET")
    # frontend database info should also be readable by apache
    env.Command(os.path.join(env['confdir'], os.path.basename(frontend)),
                frontend,
                ["install -m 0400 $SOURCE $TARGET",
                 "setfacl -m u:%s:r $TARGET" % frontend_user])


def _install_directories(env):
    config = env['config']
    dirs = config.directories.keys()
    dirs.remove('install')
    dirs.remove('INCOMING')
    for key in dirs:
        env.Command(config.directories[key], None,
                    [Mkdir(config.directories[key]),
                     Chmod(config.directories[key], 0755)])
    # Set permissions for incoming directory: both backend and frontend can
    # write to this directory and any newly-created subdirectories (-d)
    backend_user = env['config'].backend['user']
    env.Command(config.directories['INCOMING'], None,
                [Mkdir(config.directories['INCOMING']),
                 Chmod(config.directories['INCOMING'], 0755),
                 "setfacl -d -m u:%s:rwx $TARGET" % frontend_user,
                 "setfacl -d -m u:%s:rwx $TARGET" % backend_user,
                 "setfacl -m u:%s:rwx $TARGET" % frontend_user])
    env.Command(os.path.join(config.directories['install'], 'README'),
                Value(env['service_name']),
                _make_readme)


def _make_readme(env, target, source):
    service_name = source[0].get_contents()
    with open(target[0].path, 'w') as f:
        print("Do not edit files in this directory directly!", file=f)
        print("Instead, check out the source files for the %s service,"
              % service_name, file=f)
        print("and run 'scons' to install them here.", file=f)

def _make_script(env, target, source):
    name = os.path.basename(str(target[0]))
    if name.endswith('.py'):
        name = name[:-3]
    with open(target[0].path, 'w') as f:
        print("#!/usr/bin/python", file=f)
        print("import webservice", file=f)
        print("import saliweb.backend." + name, file=f)
        print("saliweb.backend.%s.main(webservice)" % name, file=f)
    env.Execute(Chmod(target[0], 0700))


def _make_cgi_script(env, target, source):
    name = os.path.basename(str(target[0]))
    modname = source[0].get_contents()
    perldir = source[1].get_contents()
    if name.endswith('.cgi'):
        name = name[:-4]
    with open(target[0].path, 'w') as f:
        print("#!/usr/bin/perl -w", file=f)
        print('BEGIN { @INC = ("%s",@INC); }' % perldir, file=f)
        print("use %s;" % modname, file=f)
        if name == 'job':  # Set up REST interface
            print("use saliweb::frontend::RESTService;", file=f)
            print("@%s::ISA = qw(saliweb::frontend::RESTService);"
                  % modname, file=f)
            print("my $m = new %s;" % modname, file=f)
            print("if ($m->cgi->request_method eq 'POST') {", file=f)
            print("    $m->display_submit_page();", file=f)
            print("} else {", file=f)
            print("    $m->display_results_page();", file=f)
            print("}", file=f)
        else:
            print("my $m = new %s;" % modname, file=f)
            print("$m->display_%s_page();" % name, file=f)
    env.Execute(Chmod(target[0], 0755))


def _make_web_service(env, target, source):
    config = source[0].get_contents()
    modname = source[1].get_contents()
    pydir = source[2].get_contents()
    version = source[3].get_contents()
    if version != 'None':
        version = "r'%s'" % version
    else:
        version = None
    with open(target[0].path, 'w') as f:
        print("config = '%s'" % config, file=f)
        print("pydir = '%s'" % pydir, file=f)
        print("import sys", file=f)
        print("sys.path.insert(0, pydir)", file=f)
        print("import %s" % modname, file=f)
        print("def get_web_service(config):", file=f)
        print("    ws = %s.get_web_service(config)" % modname, file=f)
        print("    ws.version = %s" % version, file=f)
        print("    return ws", file=f)


def _InstallAdminTools(env, tools=None):
    if tools is None:
        # todo: this list should be auto-generated from backend
        tools = ['resubmit', 'service', 'deljob', 'failjob', 'delete_all_jobs',
                 'list_jobs']
    for bin in tools:
        env.Command(os.path.join(env['bindir'], bin + '.py'), None,
                    _make_script)
    env.Command(os.path.join(env['bindir'], 'webservice.py'),
                [Value(env['instconfigfile']), Value(env['service_module']),
                 Value(env['pythondir']), Value(env['version'])],
                _make_web_service)


def _InstallCGIScripts(env, scripts=None):
    if scripts is None:
        # todo: this list should be auto-generated from backend
        scripts = ['help.cgi', 'index.cgi', 'queue.cgi', 'results.cgi',
                   'submit.cgi', 'download.cgi', 'job']
    for bin in scripts:
        env.Command(os.path.join(env['cgidir'], bin),
                    [Value(env['service_module']),
                     Value(env['perldir'])],
                    _make_cgi_script)


def _InstallPython(env, files, subdir=None):
    dir = os.path.join(env['pythondir'], env['service_module'])
    if subdir:
        dir = os.path.join(dir, subdir)
    env.Install(dir, files)


def _InstallHTML(env, files, subdir=None):
    dir = env['htmldir']
    if subdir:
        dir = os.path.join(dir, subdir)
    env.Install(dir, files)


def _InstallFrontend(env, files, subdir=None):
    dir = os.path.join(env['frontenddir'], env['service_module'])
    if subdir:
        dir = os.path.join(dir, subdir)
    env.Install(dir, files)


def _subst_python_install(env, target, source):
    fin = open(source[0].path, 'r')
    fout = open(target[0].path, 'w')
    configfile = source[1].get_contents()
    version = source[2].get_contents()
    frontenddir = source[3].get_contents()
    service_module = source[4].get_contents()
    wsgi = source[5].get_contents()
    version = 'None' if version == 'None' else "'%s'" % version
    for line in fin:
        line = line.replace('"##CONFIG##"', "'%s', %s" % (configfile, version))
        fout.write(line)
    fin.close()
    fout.close()
    # Create or touch wsgi file
    with open(wsgi, 'w') as fh:
        fh.write("import sys; sys.path.insert(0, %s)\n" % repr(frontenddir))
        fh.write("from %s import app as application\n" % service_module)


def _InstallPythonFrontend(env, files, subdir=None):
    dir = os.path.join(env['frontenddir'], env['service_module'])
    if subdir:
        dir = os.path.join(dir, subdir)
    wsgi = os.path.join(env['instdir'], env['service_module'] + ".wsgi")
    for f in files:
        env.Command(os.path.join(dir, f),
                    [f, env.Value(env['instconfigfile']),
                     env.Value(env['version']),
                     env.Value(env['frontenddir']),
                     env.Value(env['service_module']),
                     env.Value(wsgi)],
                    _subst_python_install)


def _InstallTXT(env, files, subdir=None):
    dir = env['txtdir']
    if subdir:
        dir = os.path.join(dir, subdir)
    env.Install(dir, files)


def _subst_install(env, target, source):
    fin = open(source[0].path, 'r')
    fout = open(target[0].path, 'w')
    configfile = source[1].get_contents()
    version = source[2].get_contents()
    if version != 'None':
        version = "'%s'" % version
    else:
        version = 'undef'
    service_name = source[3].get_contents()
    frontend = source[4].get_contents()
    if frontend == '':
        frontend = 'undef'
    else:
        frontend = "'" + frontend + "'"
    for line in fin:
        line = line.replace('"##CONFIG##"', "'%s', %s, '%s', %s" \
                            % (configfile, version, service_name, frontend))
        fout.write(line)
    fin.close()
    fout.close()
    env.Execute(Chmod(target[0], 0755))


def _InstallCGI(env, files, subdir=None):
    dir = env['cgidir']
    if subdir:
        dir = os.path.join(dir, subdir)
    for f in files:
        env.Command(os.path.join(dir, f),
                    [f, env.Value(env['instconfigfile']),
                     env.Value(env['version']),
                     env.Value(env['service_name']),
                     env.Value('')],
                    _subst_install)


def _InstallPerl(env, files, subdir=None):
    dir = env['perldir']
    if subdir:
        dir = os.path.join(dir, subdir)
    for f in files:
        modname = os.path.splitext(f)[0]
        if modname in env['config'].frontends:
            service_name = env['config'].frontends[modname]['service_name']
            frontend = env.Value(modname)
        else:
            service_name = env['service_name']
            frontend = env.Value('')
        env.Command(os.path.join(dir, f),
                    [f, env.Value(env['instconfigfile']),
                     env.Value(env['version']),
                     env.Value(service_name), frontend],
                    _subst_install)

class _Frontend(object):
    def __init__(self, env, name):
        if name not in env['config'].frontends:
            raise ValueError("No frontend:%s section found in config file" \
                             % name)
        self._env = e = env.Clone()
        self._name = name

        e['cgidir'] = os.path.join(env['instdir'], name, 'cgi')
        e['htmldir'] = os.path.join(env['instdir'], name, 'html')
        e['frontenddir'] = os.path.join(env['instdir'], name, 'frontend')
        e['txtdir'] = os.path.join(env['instdir'], name, 'txt')
        e['service_module'] = name

    def InstallCGIScripts(self, scripts=None):
        return _InstallCGIScripts(self._env, scripts)

    def InstallHTML(self, files, subdir=None):
        return _InstallHTML(self._env, files, subdir)

    def InstallFrontend(self, files, subdir=None):
        return _InstallFrontend(self._env, files, subdir)

    def InstallPythonFrontend(self, files, subdir=None):
        return _InstallPythonFrontend(self._env, files, subdir)

    def InstallTXT(self, files, subdir=None):
        return _InstallTXT(self._env, files, subdir)


def _make_frontend(env, name):
    return _Frontend(env, name)
