"""Simple SCons-based build system for web services.

   Build scripts should be run as the backend user; permissions should be set
   correctly for this user, with extra permissions added for the frontend
   user (apache), automatically by the build system.

todo:
- check backend and frontend DB config is readable only by us and is not in SVN
- Method to get latest svnversion
- automatic setup of database schema and users
- make sure that incoming directory is on a local disk, running etc. on netapp
"""

try:
    import MySQLdb
except ImportError, detail:
    MySQLdb = detail
import warnings
import sys
import os.path
import pwd
import saliweb.backend
import SCons.Script
from SCons.Script import File, Mkdir, Chmod, Value, Action
import subprocess
import tempfile
import re

frontend_user = 'apache'

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

def Environment(variables, configfiles, version=None):
    buildmap = _add_build_variable(variables, configfiles)
    env = SCons.Script.Environment(variables=variables)
    configfile = buildmap[env['build']]
    env['configfile'] = File(configfile)
    env['config'] = config = saliweb.backend.Config(configfile)
    _setup_sconsign(env)
    _setup_version(env, version)
    _setup_service_name(env, config)
    _setup_install_directories(env)
    if not env.GetOption('clean') and not env.GetOption('help'):
        _check(env)
    _install_config(env)
    _install_directories(env)
    env.AddMethod(_InstallAdminTools, 'InstallAdminTools')
    env.AddMethod(_InstallCGIScripts, 'InstallCGIScripts')
    env.AddMethod(_InstallPython, 'InstallPython')
    env.AddMethod(_InstallHTML, 'InstallHTML')
    env.AddMethod(_InstallTXT, 'InstallTXT')
    env.AddMethod(_InstallCGI, 'InstallCGI')
    env.AddMethod(_InstallPerl, 'InstallPerl')
    check = env.Command('check', None,
                        Action(_install_check, 'Check installation ...'))
    env.AlwaysBuild(check)
    env.Requires('/', check)
    env.Default('/')
    return env

def _install_check(target, source, env):
    """Check the final installation for sanity"""
    _check_perl_import(env)
    _check_python_import(env)

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
                      "in the SConscripts to install it. " % (modfile, modname))

def _setup_sconsign(env):
    if not os.path.exists('.scons'):
        os.mkdir('.scons')
    env.SConsignFile('.scons/sconsign.dblite')

def _setup_version(env, version):
    if version is None:
        svnversion = env.WhereIs('svnversion')
        if svnversion:
            try:
                p = subprocess.Popen(svnversion, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)
                ret = p.communicate()
                if p.returncode:
                    raise OSError("returned exit code %d, stdout %s, "
                                  "stderr %s" \
                                  % (p.returncode, ret[0], ret[1]))
                v = ret[0].split('\n')[0]
                if v and v != 'exported':
                    version = 'r' + v
            except OSError, detail:
                warnings.warn("Could not run %s: %s" \
                              % (svnversion, str(detail)))
        else:
            warnings.warn("Could not find 'svnversion' binary in path")
    env['version'] = version

def _setup_service_name(env, config):
    env['service_name'] = config.service_name
    env['service_module'] = config.service_name.lower().replace(' ', '_')

def _setup_install_directories(env):
    config = env['config']
    env['instdir'] = config.directories['install']
    env['bindir'] = os.path.join(env['instdir'], 'bin')
    env['confdir'] = os.path.join(env['instdir'], 'conf')
    env['pythondir'] = os.path.join(env['instdir'], 'python')
    env['htmldir'] = os.path.join(env['instdir'], 'html')
    env['txtdir'] = os.path.join(env['instdir'], 'txt')
    env['cgidir'] = os.path.join(env['instdir'], 'cgi')
    env['perldir'] = os.path.join(env['instdir'], 'lib')

def _check(env):
    _check_user(env)
    _check_permissions(env)
    _check_directories(env)
    if isinstance(MySQLdb, Exception):
        print >> sys.stderr, "Could not import the MySQLdb module: %s" % MySQLdb
        print >> sys.stderr, "This module is needed by the backend."
        env.Exit(1)
    _check_mysql(env)
    _check_crontab(env)
    _check_service(env)

def _check_directories(env):
    _check_directory_locations(env)
    _check_directory_permissions(env)

def _check_directory_locations(env):
    incoming = env['config'].directories['INCOMING']
    if not incoming.startswith('/modbase') and not incoming.startswith('/usr') \
       and not incoming.startswith('/var') and not incoming.startswith('/home'):
        print >> sys.stderr, """
** The INCOMING directory is set to %s.
** It must be on a local disk (e.g. /modbase1).
""" % incoming
        env.Exit(1)

    running = env['config'].directories['RUNNING']
    if not running.startswith('/netapp'):
        print >> sys.stderr, """
** The RUNNING directory is set to %s.
** It must be on a cluster-accessible disk (i.e. /netapp).
""" % running
        env.Exit(1)

def _check_directory_permissions(env):
    backend_user = env['config'].backend['user']
    for dir in env['config'].directories.values():
        if not os.path.exists(dir): continue
        out, err = subprocess.Popen(['/usr/bin/getfacl', dir],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE).communicate()
        if not re.search('^# owner: ' + backend_user, out,
                         re.MULTILINE | re.DOTALL):
            print >> sys.stderr, """
** Install directory %s is not owned by the backend user, %s!
** Please change the ownership of this directory.
""" % (dir, backend_user)
            env.Exit(1)
        if not re.search('^group::.\-..*other::.\-.', out,
                         re.MULTILINE | re.DOTALL):
            print >> sys.stderr, """
** Install directory %s appears to be group- or world-writable!
** It should only be writable by the backend user, %s.
** To fix this, run
   chmod 755 %s
""" % (dir, backend_user, dir)
            env.Exit(1)


def _check_user(env):
    backend_user = env['config'].backend['user']
    current_user = pwd.getpwuid(os.getuid()).pw_name
    if backend_user != current_user:
        print >> sys.stderr, """
scons must be run as the backend user, which is '%s' according to the
config file, %s.
You are currently trying to run scons as the '%s' user.
Please run again with something like \"/usr/bin/sudo -u %s scons\"
""" % (backend_user, env['configfile'], current_user, backend_user)
        env.Exit(1)

def _check_permissions(env):
    """Make sure we can write to the .scons directory, and read the
       database configuration files"""
    try:
        open('.scons/.test', 'w')
        os.unlink('.scons/.test')
    except IOError, detail:
        print >> sys.stderr, """
** Cannot write to .scons directory: %s
** The backend user needs to be able to write to this directory.
** To fix this problem, make sure that your checkout is on a local disk
** (e.g. /modbase1, /modbase2, etc., not /netapp) and run
   setfacl -m u:%s:rwx .scons
""" % (str(detail), env['config'].backend['user'])
        env.Exit(1)
    for end in ('back', 'front'):
        conf = env['config'].database['%send_config' % end]
        if not os.path.exists(conf): continue
        out, err = subprocess.Popen(['/usr/bin/getfacl', conf],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE).communicate()
        if not re.search('^group::\-\-\-.*^other::\-\-\-', out,
                         re.MULTILINE | re.DOTALL):
            print >> sys.stderr, """
** The database configuration file %s appears to be group- or world-
** readable or writable. It should only be user readable and writable.
** To fix this, run
   chmod 0600 %s
""" % (conf, conf)
            env.Exit(1)
        dir, base = os.path.split(conf)
        svnbase = os.path.join(dir, '.svn', 'text-base', base + '.svn-base')
        if os.path.exists(svnbase):
            print >> sys.stderr, """
** The database configuration file %s appears to be under SVN control.
** Please do not put files containing sensitive information (i.e. passwords)
** under SVN control.
** To fix this, run
   svn rm %s; svn ci %s
** Then recreate %s using a fresh password.
""" % (conf, conf, conf, conf)
            env.Exit(1)
        try:
            open(conf)
        except IOError, detail:
            print >> sys.stderr, """
** Cannot read database configuration file: %s
** The backend user needs to be able to read this file.
** To fix this problem, make sure that your checkout is on a local disk
** (e.g. /modbase1, /modbase2, etc., not /netapp) and run
   setfacl -m u:%s:r %s
""" % (str(detail), env['config'].backend['user'], conf)
            env.Exit(1)

def _format_shell_command(env, cmd):
    sudo_user = os.environ.get('SUDO_USER')
    if sudo_user and sudo_user != env['config'].backend['user']:
        return "/usr/bin/sudo -u %s " % env['config'].backend['user'] + cmd
    else:
        return cmd

def _check_crontab(env):
    """Make sure that a crontab is set up to run the service."""
    binary = os.path.join(env['bindir'], 'service.py')
    if not _found_binary_in_crontab(binary):
        print "** To make your web service active, add the following to "
        print "** the backend user's crontab;"
        print "** use " + _format_shell_command(env, "crontab -e") \
              + " to edit it:"
        print "0 * * * * " + binary + " condstart > /dev/null"
        print

def _check_service(env):
    config = env['config']
    db = saliweb.backend.Database(saliweb.backend.Job)
    ws = saliweb.backend.WebService(config, db)
    try:
        pid = ws.get_running_pid()
        if pid is not None:
            binary = os.path.join(env['bindir'], 'service.py')
            print "** Backend daemon is currently running. Run"
            print "   " + _format_shell_command(env, "%s restart" % binary)
            print "** to restart it to pick up any changes."
    except saliweb.backend.StateFileError, detail:
        print "** Backend daemon will not start due to a previous failure. "
        print "** You will need to fix this manually before it will run again."
        print "** Refer to %s for more information" % config.state_file

def _found_binary_in_crontab(binary):
    """See if the given binary is run from the user's crontab"""
    p = subprocess.Popen(['/usr/bin/crontab', '-l'], stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)

    binre = re.compile('\s*[^#].*' + binary + ' condstart > /dev/null$')
    match = False
    for line in p.stdout:
        if binre.match(line):
            match = True
    err = p.stderr.read()
    ret = p.wait()
    if ret != 0:
        raise OSError("crontab -l exited with code %d and stderr %s" \
                      % (ret, err))
    return match

def _check_mysql(env):
    """Make sure that we can connect to the database as both the frontend and
       backend users. todo: make sure the DB schema matches the backend;
       make sure the backend and frontend DB users have the correct permissions.
    """
    c = env['config']
    c._read_db_auth('back')
    backend = dict(c.database)
    c._read_db_auth('front')
    frontend = dict(c.database)

    try:
        db = MySQLdb.connect(db=c.database['db'], user=backend['user'],
                             passwd=backend['passwd'])
        cur = db.cursor()
        cur.execute('DESCRIBE jobs')
        _check_mysql_schema(env, cur)
        cur.execute('SHOW GRANTS')
#       for row in cur:
#           print row

        db = MySQLdb.connect(db=c.database['db'], user=frontend['user'],
                             passwd=frontend['passwd'])
        cur = db.cursor()
#       cur.execute('SHOW GRANTS')
#       for row in cur:
#           print row
    except (MySQLdb.OperationalError, MySQLdb.ProgrammingError), detail:
        outfile = _generate_admin_mysql_script(c.database['db'], backend,
                                               frontend)
        print >> sys.stderr, """
** Could not query the jobs table in the %s database using both the
** frontend and backend users. The actual error message follows:
** %s
** This generally means that the web service is not set up correctly
** for MySQL. Please ask a sysadmin to run the commands in the file
** %s to set this up properly.
""" % (c.database['db'], str(detail), outfile)
        env.Exit(1)

def _generate_admin_mysql_script(database, backend, frontend):
    d = saliweb.backend.Database(None)
    fd, outfile = tempfile.mkstemp()
    commands = """CREATE DATABASE %(database)s
GRANT DELETE,CREATE,DROP,INDEX,INSERT,SELECT,UPDATE ON %(database)s.* TO '%(backend_user)s'@'localhost' IDENTIFIED BY '%(backend_passwd)s'
CREATE TABLE %(database)s.jobs (%(schema)s)
GRANT SELECT ON %(database)s.jobs to '%(frontend_user)s'@'localhost' identified by '%(frontend_passwd)s'
GRANT INSERT (name,user,passwd,directory,contact_email,url,submit_time) ON %(database)s.jobs to '%(frontend_user)s'@'localhost'
""" % {'database': database, 'backend_user': backend['user'],
       'backend_passwd': backend['passwd'], 'frontend_user': frontend['user'],
       'frontend_passwd': frontend['passwd'],
       'schema': ', '.join(x.get_schema() for x in d._fields)}
    os.write(fd, commands)
    os.close(fd)
    os.chmod(outfile, 0600)
    return outfile

def _check_mysql_schema(env, cursor):
    d = saliweb.backend.Database(None)
    dbfields = []
    for row in cursor:
        dbfields.append(saliweb.backend.MySQLField(row[0], row[1].upper(),
                                                   null=row[2], key=row[3],
                                                   default=row[4]))

    for dbfield, backfield in zip(dbfields, d._fields):
        if dbfield != backfield:
            print >> sys.stderr, """
** The 'jobs' database table schema does not match that expected by the backend;
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
""" % (dbfield.name, dbfield.name, dbfield.get_schema(), backfield.get_schema(),
       ',\n   '.join(x.get_schema() for x in d._fields))
            env.Exit(1)

    if len(dbfields) != len(d._fields):
        print >> sys.stderr, """
** The 'jobs' database table schema does not match that expected by the backend;
** it has %d fields, while the backend has %d fields. Please modify the
** table schema accordingly. The entire table schema should look like:
   %s
""" % (len(dbfields), len(d._fields),
       ',\n   '.join(x.get_schema() for x in d._fields))
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
                    Mkdir(config.directories[key]))
    # Set permissions for incoming directory: both backend and frontend can
    # write to this directory and any newly-created subdirectories (-d)
    backend_user = env['config'].backend['user']
    env.Command(config.directories['INCOMING'], None,
                [Mkdir(config.directories['INCOMING']),
                 "setfacl -d -m u:%s:rwx $TARGET" % frontend_user,
                 "setfacl -d -m u:%s:rwx $TARGET" % backend_user,
                 "setfacl -m u:%s:rwx $TARGET" % frontend_user])

def _make_script(env, target, source):
    name = os.path.basename(str(target[0]))
    if name.endswith('.py'):
        name = name[:-3]
    f = open(target[0].path, 'w')
    print >> f, "#!/usr/bin/python"
    print >> f, "import webservice"
    print >> f, "import saliweb.backend." + name
    print >> f, "saliweb.backend.%s.main(webservice)" % name
    f.close()
    env.Execute(Chmod(target, 0700))

def _make_cgi_script(env, target, source):
    name = os.path.basename(str(target[0]))
    modname = source[0].get_contents()
    if name.endswith('.cgi'):
        name = name[:-4]
    f = open(target[0].path, 'w')
    print >> f, "#!/usr/bin/perl -w"
    print >> f, 'BEGIN { @INC = ("../lib/",@INC); }'
    print >> f, "use %s;" % modname
    if name == 'job':  # Set up REST interface
        print >> f, "use saliweb::frontend::RESTService;"
        print >> f, "@%s::ISA = qw(saliweb::frontend::RESTService);" \
                    % modname
        print >> f, "my $m = new %s;" % modname
        print >> f, "if ($m->cgi->request_method eq 'POST') {"
        print >> f, "    $m->display_submit_page();"
        print >> f, "} else {"
        print >> f, "    $m->display_results_page();"
        print >> f, "}"
    else:
        print >> f, "my $m = new %s;" % modname
        print >> f, "$m->display_%s_page();" % name
    f.close()
    env.Execute(Chmod(target, 0755))

def _make_web_service(env, target, source):
    f = open(target[0].path, 'w')
    config = source[0].get_contents()
    modname = source[1].get_contents()
    pydir = source[2].get_contents()
    print >> f, "config = '%s'" % config
    print >> f, "pydir = '%s'" % pydir
    print >> f, "import sys"
    print >> f, "sys.path.insert(0, pydir)"
    print >> f, "import %s" % modname
    print >> f, "get_web_service = %s.get_web_service" % modname

def _InstallAdminTools(env, tools=None):
    if tools is None:
        # todo: this list should be auto-generated from backend
        tools = ['resubmit', 'service']
    for bin in tools:
        env.Command(os.path.join(env['bindir'], bin + '.py'), None,
                    _make_script)
    env.Command(os.path.join(env['bindir'], 'webservice.py'),
                [Value(env['instconfigfile']), Value(env['service_module']),
                 Value(env['pythondir'])], _make_web_service)

def _InstallCGIScripts(env, scripts=None):
    if scripts is None:
        # todo: this list should be auto-generated from backend
        scripts = ['help.cgi', 'index.cgi', 'queue.cgi', 'results.cgi',
                   'submit.cgi', 'job']
    for bin in scripts:
        env.Command(os.path.join(env['cgidir'], bin),
                    Value(env['service_module']),
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
    service_name = source[3].get_contents()
    for line in fin:
        line = line.replace('@CONFIG@', "'%s', '%s', '%s'" \
                               % (configfile, version, service_name))
        fout.write(line)
    fin.close()
    fout.close()
    env.Execute(Chmod(target, 0755))

def _InstallCGI(env, files, subdir=None):
    dir = env['cgidir']
    if subdir:
        dir = os.path.join(dir, subdir)
    for f in files:
        env.Command(os.path.join(dir, f),
                    [f, env.Value(env['instconfigfile']),
                     env.Value(env['version']),
                     env.Value(env['service_name'])],
                    _subst_install)

def _InstallPerl(env, files, subdir=None):
    dir = env['perldir']
    if subdir:
        dir = os.path.join(dir, subdir)
    for f in files:
        env.Command(os.path.join(dir, f),
                    [f, env.Value(env['instconfigfile']),
                     env.Value(env['version']),
                     env.Value(env['service_name'])],
                    _subst_install)
