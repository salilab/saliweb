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
import sys
import os.path
import pwd
import saliweb.backend
import SCons.Script
from SCons.Script import File, Mkdir, Chmod, Value
import subprocess
import re

frontend_user = 'apache'
backend_user = pwd.getpwuid(os.getuid()).pw_name

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

def Environment(variables, configfiles, service_name=None):
    buildmap = _add_build_variable(variables, configfiles)
    env = SCons.Script.Environment(variables=variables)
    configfile = buildmap[env['build']]
    env['configfile'] = File(configfile)
    env['config'] = config = saliweb.backend.Config(configfile)
    if service_name is None:
        env['service_name'] = config.service_name.lower()
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
    env.Default(env['instdir'])
    return env

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
    if isinstance(MySQLdb, Exception):
        print >> sys.stderr, "Could not import the MySQLdb module: %s" % MySQLdb
        print >> sys.stderr, "This module is needed by the backend."
        env.Exit(1)
    _check_mysql(env)
    _check_crontab(env)
    _check_service(env)

def _check_crontab(env):
    """Make sure that a crontab is set up to run the service."""
    binary = os.path.join(env['bindir'], 'service.py')
    if not _found_binary_in_crontab(binary):
        print "To make your web service active, add the following to "
        print "your crontab (use crontab -e to edit it):"
        print
        print "0 * * * * " + binary + " condstart > /dev/null"

def _check_service(env):
    config = env['config']
    db = saliweb.backend.Database(saliweb.backend.Job)
    ws = saliweb.backend.WebService(config, db)
    try:
        pid = ws.get_running_pid()
        if pid is not None:
            binary = os.path.join(env['bindir'], 'service.py')
            print "Backend daemon is currently running. Run"
            print "%s restart" % binary
            print "to restart it to pick up any changes."
    except saliweb.backend.StateFileError, detail:
        print "Backend daemon will not start due to a previous failure. "
        print "You will need to fix this manually before it will run again."
        print "Refer to %s for more information" % config.state_file

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

    db = MySQLdb.connect(db=c.database['db'], user=backend['user'],
                         passwd=backend['passwd'])
    cur = db.cursor()
    cur.execute('DESCRIBE jobs')
#   for row in cur:
#       print row
    cur.execute('SHOW GRANTS')
#   for row in cur:
#       print row

    db = MySQLdb.connect(db=c.database['db'], user=frontend['user'],
                         passwd=frontend['passwd'])
    cur = db.cursor()
    cur.execute('SHOW GRANTS')
#   for row in cur:
#       print row


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
    if name.endswith('.cgi'):
        name = name[:-4]
    f = open(target[0].path, 'w')
    print >> f, "#!/usr/bin/perl -w"
    print >> f, 'BEGIN { @INC = ("../lib/",@INC); }'
    print >> f, "use %s" % env['service_name']
    print >> f, "my $m = new %s" % env['service_name']
    print >> f, "$m->display_%s_page()" % name
    f.close()
    env.Execute(Chmod(target, 0700))

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
                [Value(env['instconfigfile']), Value(env['service_name']),
                 Value(env['pythondir'])], _make_web_service)

def _InstallCGIScripts(env, scripts=None):
    if scripts is None:
        # todo: this list should be auto-generated from backend
        scripts = ['help', 'index', 'queue', 'results', 'submit']
    for bin in scripts:
        env.Command(os.path.join(env['cgidir'], bin + '.py'), None,
                    _make_cgi_script)

def _InstallPython(env, files, subdir=None):
    dir = os.path.join(env['pythondir'], env['service_name'])
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
    configfile = env['instconfigfile']
    for line in fin:
        line = line.replace('@CONFIGFILE@', "'" + configfile + "'")
        fout.write(line)
    fin.close()
    fout.close()
    env.Execute(Chmod(target, 0755))

def _InstallCGI(env, files, subdir=None):
    dir = env['cgidir']
    if subdir:
        dir = os.path.join(dir, subdir)
    for f in files:
        env.Command(os.path.join(dir, f), f, _subst_install)

def _InstallPerl(env, files, subdir=None):
    dir = env['perldir']
    if subdir:
        dir = os.path.join(dir, subdir)
    for f in files:
        env.Command(os.path.join(dir, f), f, _subst_install)
