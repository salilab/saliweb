from __future__ import print_function
from optparse import OptionParser
import string
import random
import os
import sys
import pwd
import subprocess

def _run_command(prefix, cmd, cwd):
    print(prefix + " " + " ".join(cmd))
    ret = subprocess.call([prefix] + cmd, cwd=cwd)
    if ret != 0:
        raise OSError("subprocess failed with code %d" % ret)

class SVNSourceControl(object):
    def __init__(self, short_name, topdir):
        self.short_name = short_name
        self.topdir = topdir
        self.svn_url = 'https://svn.salilab.org/' + short_name
        self.svn_trunk_url = self.svn_url + '/trunk'

    def _run_svn_command(self, cmd, cwd=None):
        _run_command('svn', cmd, cwd)

    def setup(self):
        self._run_svn_command(['mkdir', self.svn_trunk_url,
                               '-m', 'Make trunk directory'])
        self._run_svn_command(['co', self.svn_trunk_url, self.short_name])

    def commit(self):
        self._run_svn_command(['add', 'test', 'txt', 'SConstruct', 'python',
                               'lib'], cwd=self.topdir)
        self._run_svn_command(['add', '-N', 'conf'], cwd=self.topdir)
        self._run_svn_command(['add', 'conf/live.conf'], cwd=self.topdir)
        self._run_svn_command(['propset', 'svn:ignore', '.scons', '.'],
                              cwd=self.topdir)
        self._run_svn_command(['propset', 'svn:ignore',
                               'frontend.conf\nbackend.conf', 'conf'],
                              cwd=self.topdir)
        self._run_svn_command(['ci', '-m', 'Initial setup'], cwd=self.topdir)


class GitSourceControl(object):
    def __init__(self, short_name, topdir):
        self.short_name = short_name
        self.topdir = topdir
        self.url = 'git@github.com:salilab/%s.git' % short_name

    def _run_git_command(self, cmd, cwd=None):
        _run_command('git', cmd, cwd)

    def setup(self):
        self._run_git_command(['clone', self.url])

    def commit(self):
        # Ignore files
        with open(os.path.join(self.topdir, '.gitignore'), 'w') as fh:
            fh.write(".scons\n*.pyc\n")
        with open(os.path.join(self.topdir, 'conf', '.gitignore'), 'w') as fh:
            fh.write("frontend.conf\nbackend.conf\n")
        def list_dir(subdir):
            files = os.listdir(os.path.join(self.topdir, subdir))
            return [os.path.join(subdir, f) for f in files]
        files = list_dir('test/frontend') + list_dir('test/backend') \
                + list_dir(os.path.join('frontend', self.short_name)) \
                + list_dir(os.path.join('frontend', self.short_name,
                                        'templates')) \
                + list_dir(os.path.join('backend', self.short_name)) \
                + ['SConstruct', 'test/SConscript', '.gitignore',
                   'conf/.gitignore', 'conf/live.conf']
        self._run_git_command(['add'] + files, cwd=self.topdir)
        self._run_git_command(['commit', '-m', 'Initial setup'],
                              cwd=self.topdir)
        self._run_git_command(['push', '-u', 'origin', 'master'],
                              cwd=self.topdir)


class MakeWebService(object):

    def __init__(self, short_name, service_name, git):
        self.short_name = short_name
        self.topdir = self.short_name
        self.user = self.short_name
        self.db = self.short_name
        if git:
            self.source_control = GitSourceControl(short_name, self.topdir)
        else:
            self.source_control = SVNSourceControl(short_name, self.topdir)
        self.service_name = service_name
        self.db_frontend_user = self._make_database_name("front")
        self.db_backend_user = self._make_database_name("back")
        self.install = self._get_install_dir()

    def _make_database_name(self, typ):
        """Generate a MySQL database username"""
        suffix = "_" + typ + "end"
        prefix = self.short_name
        max_length = 16 # MySQL max username length
        while True:
            name = prefix + suffix
            if len(name) <= max_length:
                return name
            # Trim suffix if necessary first, down to the minimum necessary
            # to be unique ("_f" or "_b").
            elif len(suffix) > 2:
                suffix = suffix[:-1]
            # Then trim too-long short_names
            else:
                prefix = prefix[:-1]

    def make(self):
        self.source_control.setup()
        self._make_directories()
        self._make_sconstruct()
        self._make_sconscripts()
        self._make_config()
        self._make_frontend()
        self._make_backend()
        self._make_templates()
        self._make_tests()
        self.source_control.commit()
        self._print_completion()

    def _print_completion(self):
        uid = pwd.getpwnam(self.user).pw_uid
        print("Web service set up in %s directory" % self.topdir,
              file=sys.stderr)
        print("""Still need to:
1. Add access to the %(user)s account to users by running
/usr/bin/sudo /usr/sbin/visudo
and adding lines such as
ben     modbase=(%(user)s) ALL

2. Make accounts for %(user)s on the cluster(s) if it's going
to run cluster jobs, and make the the /wynton/home/sali/%(user)s directory.

3. Change into the %(topdir)s directory and run
/usr/bin/sudo -u %(user)s scons
until it works.
""" % {'user': self.user, 'topdir': self.topdir, 'uid': uid}, file=sys.stderr)

    def _make_password(self, length):
        return "".join(random.choice(string.ascii_letters + string.digits) \
               for x in range(length))

    def _get_install_dir(self):
        try:
            dir = pwd.getpwnam(self.user).pw_dir
        except KeyError:
            print("""The %(user)s user doesn't exist. Please create it first:

1. Determine the UID for the new user and add it to the wiki page:
https://salilab.org/internal/wiki/SysAdmin/UID

2. Set up the %(user)s user and group by running
/usr/bin/sudo /usr/sbin/groupadd -g <UID> %(user)s
/usr/bin/sudo /usr/sbin/useradd -u <UID> -g <UID> -c '%(user)s service' -d %(dir)s %(user)s
/usr/bin/sudo chmod a+rx ~%(user)s
""" % {'user': self.user, 'dir': '/modbase5/home/%s' % self.user})
            sys.exit(1)
        return os.path.join(dir, 'service')

    def _make_directories(self):
        for subdir in ('conf', 'frontend', 'backend', 'test',
                       'test/frontend', 'test/backend'):
            os.mkdir(os.path.join(self.topdir, subdir))
        os.mkdir(os.path.join(self.topdir, 'frontend', self.short_name))
        os.mkdir(os.path.join(self.topdir, 'frontend', self.short_name,
                              'templates'))
        os.mkdir(os.path.join(self.topdir, 'backend', self.short_name))

    def _make_sconstruct(self):
        envmodule = ", service_module='%s'" % self.short_name
        with open(os.path.join(self.topdir, 'SConstruct'), 'w') as f:
            print("""import saliweb.build

vars = Variables('config.py')
env = saliweb.build.Environment(vars, ['conf/live.conf']%s)
Help(vars.GenerateHelpText(env))

env.InstallAdminTools()

Export('env')
SConscript('frontend/%s/SConscript')
SConscript('backend/%s/SConscript')
SConscript('test/SConscript')""" % (envmodule, self.short_name,
                                    self.short_name), file=f)

    def _make_sconscripts(self):
        with open(os.path.join(self.topdir, 'backend', self.short_name,
                               'SConscript'), 'w') as f:
            print("""Import('env')

env.InstallPython(['__init__.py'])""", file=f)

        with open(os.path.join(self.topdir, 'frontend', self.short_name,
                               'SConscript'), 'w') as f:
            print("""Import('env')

SConscript('templates/SConscript')

env.InstallPythonFrontend(['__init__.py'])""", file=f)

        with open(os.path.join(self.topdir, 'frontend', self.short_name,
                               'templates', 'SConscript'), 'w') as f:
            print("""Import('env')

env.InstallFrontend(['layout.html', 'index.html', 'help.html', 'contact.html'],
                    'templates')""", file=f)

        with open(os.path.join(self.topdir, 'test', 'backend',
                               'SConscript'), 'w') as f:
            print("""Import('env')

env.RunPythonTests(Glob("*.py"))""", file=f)

        with open(os.path.join(self.topdir, 'test', 'frontend',
                               'SConscript'), 'w') as f:
            print("""Import('env')

env.RunPythonFrontendTests(Glob("*.py"))""", file=f)

        with open(os.path.join(self.topdir, 'test',
                               'SConscript'), 'w') as f:
            print("""SConscript('backend/SConscript')
SConscript('frontend/SConscript')""", file=f)

    def _make_config(self):
        with open(os.path.join(self.topdir, 'conf', 'live.conf'), 'w') as f:
            print("""[general]
admin_email: %(user)s@salilab.org
socket: %(install)s/%(short_name)s.socket
service_name: %(service_name)s
urltop: https://modbase.compbio.ucsf.edu/%(short_name)s

[backend]
user: %(short_name)s
state_file: %(install)s/%(short_name)s.state
check_minutes: 10

[database]
backend_config: backend.conf
frontend_config: frontend.conf
db: %(db)s

[directories]
install: %(install)s
incoming: %(install)s/incoming/
preprocessing: /wynton/home/sali/%(user)s/running/
completed: %(install)s/completed/
failed: %(install)s/failed/

[oldjobs]
archive: 7d
expire: 30d""" % self.__dict__, file=f)
        for (end, user) in (('frontend', self.db_frontend_user),
                            ('backend', self.db_backend_user)):
            fname = os.path.join(self.topdir, 'conf', '%s.conf' % end)
            passwd = self._make_password(20)
            with open(fname, 'w') as f:
                print("""[%s_db]
user: %s
passwd: %s""" % (end, user, passwd), file=f)
            os.chmod(fname, 0o600)

    def _make_frontend(self):
        with open(os.path.join(self.topdir, 'frontend', self.short_name,
                               '__init__.py'), 'w') as f:
            print("""from flask import render_template, request
import saliweb.frontend

parameters = []
app = saliweb.frontend.make_application(__name__, parameters)

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/contact')
def contact():
    return render_template('contact.html')


@app.route('/help')
def help():
    return render_template('help.html')


@app.route('/job', methods=['GET', 'POST'])
def job():
    if request.method == 'GET':
        return saliweb.frontend.render_queue_page()
    else:
        pass  # todo
""", file=f)

    def _make_backend(self):
        with open(os.path.join(self.topdir, 'backend', self.short_name,
                               '__init__.py'), 'w') as f:
            print("""import saliweb.backend

class Job(saliweb.backend.Job):

    def run(self):
        # TODO


def get_web_service(config_file):
    db = saliweb.backend.Database(Job)
    config = saliweb.backend.Config(config_file)
    return saliweb.backend.WebService(config, db)
""", file=f)

    def _make_tests(self):
        with open(os.path.join(self.topdir, 'test', 'frontend',
                               'test_frontend.py'), 'w') as f:
            print("""import unittest
import saliweb.test

# Import the %s frontend with mocks
%s = saliweb.test.import_mocked_frontend("%s", __file__,
                                           '../../frontend')


class Tests(saliweb.test.TestCase):

    def test_index(self):
        "Test index page"
        c = %s.app.test_client()
        rv = c.get('/')
        self.assertIn('Main Page', rv.data)


if __name__ == '__main__':
    unittest.main()
""" % ((self.short_name,)*4), file=f)

    def _make_templates(self):
        template_dir = os.path.join(self.topdir, 'frontend',
                                    self.short_name, 'templates')
        with open(os.path.join(template_dir, 'layout.html'), 'w') as f:
            print("""{% extends "saliweb/layout.html" %}

{% block navigation %}
{{ get_navigation_links(
       [(url_for("index"), "Home"),
        (url_for("job"), "Queue"),
        (url_for("help"), "Help"),
        (url_for("contact"), "Contact")])
}}
{% endblock %}

{% block sidebar %}
<p>Sidebar</p>
{% endblock %}

{% block footer %}
<p>Footer</p>
{% endblock %}
""", file=f)

        with open(os.path.join(template_dir, 'index.html'), 'w') as f:
            print("""{%% extends "layout.html" %%}

{%% block title %%}%s{%% endblock %%}

{%% block body %%}
<h1>Main Page</h1>
{%% endblock %%}
""" % self.service_name, file=f)

        with open(os.path.join(template_dir, 'contact.html'), 'w') as f:
            print("""{%% extends "layout.html" %%}

{%% block title %%}%s Contact{%% endblock %%}

{%% block body %%}
<p>Please address inquiries to:<br />
<script type="text/javascript">escramble('%s','salilab.org')</script></p>
{%% endblock %%}
""" % (self.service_name, self.user), file=f)

        with open(os.path.join(template_dir, 'help.html'), 'w') as f:
            print("""{%% extends "layout.html" %%}

{%% block title %%}%s Help{%% endblock %%}

{%% block body %%}
<h1>Help</h1>
{%% endblock %%}
""" % self.service_name, file=f)


def get_options():
    parser = OptionParser()
    parser.set_usage("""
%prog [-h] [--git|--svn] SHORT_NAME SERVICE_NAME

Set up a directory structure for a new web service called "SERVICE_NAME".
"SERVICE_NAME" should be the human-readable name of the web service, for
example "ModFoo" or "Peptide Docking". It may contain spaces and mixed case.

"SHORT_NAME" should be a short name containing only lowercase letters and
no spaces. This name is used to name the directory containing the files,
the generated Python and Perl modules, system and MySQL users etc.
An SVN (--svn option) or git (--git) repository with the same name is
assumed to already exist, but to be empty (e.g. if SHORT_NAME is 'modfoo'
the repository should exist at https://svn.salilab.org/modfoo or
https://github.com/salilab/modfoo). A working directory with the same name is
set up, and the files checked in to the trunk of the SVN or git repository.
Users can then work on the service by checking out
the SVN trunk (e.g. "svn co https://svn.salilab.org/modfoo/trunk modfoo")
or cloning the git repository
(e.g. "git clone https://github.com/salilab/modfoo.git").

e.g.
%prog --svn pepdock "Peptide Docking"
""")
    parser.add_option("--svn", action="store_true", dest="svn",
                      default=False, help="Use an SVN repository")
    parser.add_option("--git", action="store_true", dest="git",
                      default=False, help="Use a git repository")

    opts, args = parser.parse_args()
    if len(args) != 2:
        parser.error("Wrong number of arguments given")
    if not opts.svn ^ opts.git:
        parser.error("Please specify one of --git or --svn")
    if ' ' in args[0] or args[0].lower() != args[0]:
        parser.error("SHORT_NAME must be all lowercase and contain no spaces")
    return args, opts.git


def main():
    args, git = get_options()
    m = MakeWebService(*args, git=git)
    m.make()

if __name__ == '__main__':
    main()
