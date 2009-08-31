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
import saliweb.backend
import SCons.Script
from SCons.Script import File, Mkdir, Chmod, Value

webuser = 'apache'

def Environment(configfile, service_name=None):
    env = SCons.Script.Environment()
    env['configfile'] = File(configfile)
    env['config'] = config = saliweb.backend.Config(configfile)
    if service_name is None:
        env['service_name'] = config.service_name.lower()
    _setup_install_directories(env)
    if not env.GetOption('clean') and not env.GetOption('help'):
        _check(env)
    _install_config(env)
    _install_directories(env)
    env.AddMethod(_InstallBinaries, 'InstallBinaries')
    env.AddMethod(_InstallPython, 'InstallPython')
    env.Default(env['instdir'])
    return env

def _setup_install_directories(env):
    config = env['config']
    env['instdir'] = config.directories['install']
    env['bindir'] = os.path.join(env['instdir'], 'bin')
    env['confdir'] = os.path.join(env['instdir'], 'conf')
    env['pythondir'] = os.path.join(env['instdir'], 'python')

def _check(env):
    if isinstance(MySQLdb, Exception):
        print >> sys.stderr, "Could not import the MySQLdb module: %s" % MySQLdb
        print >> sys.stderr, "This module is needed by the backend."
        env.Exit(1)
    _check_mysql(env)

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
                 "setfacl -m u:%s:r $TARGET" % webuser])

def _install_directories(env):
    config = env['config']
    dirs = config.directories.keys()
    dirs.remove('install')
    for key in dirs:
        env.Command(config.directories[key], None,
                    Mkdir(config.directories[key]))

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

def _make_web_service(env, target, source):
    f = open(target[0].path, 'w')
    config = str(source[0])
    modname = source[1].get_contents()
    pydir = source[2].get_contents()
    print >> f, "config = '%s'" % config
    print >> f, "pydir = '%s'" % pydir
    print >> f, "import sys"
    print >> f, "sys.path.insert(0, pydir)"
    print >> f, "import %s" % modname
    print >> f, "get_web_service = %s.get_web_service" % modname

def _InstallBinaries(env, binaries=None):
    if binaries is None:
        # todo: this list should be auto-generated from backend
        binaries = ['resubmit', 'process_jobs']
    for bin in binaries:
        env.Command(os.path.join(env['bindir'], bin + '.py'), None,
                    _make_script)
    env.Command(os.path.join(env['bindir'], 'webservice.py'),
                [env['instconfigfile'], Value(env['service_name']),
                 Value(env['pythondir'])], _make_web_service)

def _InstallPython(env, files, subdir=None):
    dir = os.path.join(env['pythondir'], env['service_name'])
    if subdir:
        dir = os.path.join(dir, subdir)
    env.Install(dir, files)
