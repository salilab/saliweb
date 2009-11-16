from optparse import OptionParser
import string
import random
import os
import sys
import pwd

class MakeWebService(object):
    def __init__(self, service_name, short_name=None):
        self.service_name = service_name
        if short_name:
            self.short_name = short_name
        else:
            self.short_name = service_name.lower().replace(' ', '_')
        self.topdir = self.short_name
        self.user = self.short_name
        self.db = self.short_name
        self.db_frontend_user = self.short_name + '_frontend'
        self.db_backend_user = self.short_name + '_backend'
        self.install = self._get_install_dir()

    def make(self):
        self._make_directories()
        self._make_sconstruct()
        self._make_sconscripts()
        self._make_config()
        self._make_frontend()
        self._make_backend()
        self._make_txt()
        print >> sys.stderr, "Web service set up in %s directory" % self.topdir

    def _make_password(self, length):
        return "".join(random.choice(string.letters + string.digits) \
               for x in range(length))

    def _get_install_dir(self):
        try:
            dir = pwd.getpwnam(self.user).pw_dir
        except KeyError:
            dir = '/modbase5/home/%s' % self.user
        return os.path.join(dir, 'service')

    def _make_directories(self):
        os.mkdir(self.topdir)
        for subdir in ('conf', 'lib', 'python', 'txt', 'test',
                       'test/frontend', 'test/backend'):
            os.mkdir(os.path.join(self.topdir, subdir))
        os.mkdir(os.path.join(self.topdir, 'python', self.short_name))

    def _make_sconstruct(self):
        envmodule = ", service_module='%s'" % self.short_name
        f = open(os.path.join(self.topdir, 'SConstruct'), 'w')
        print >> f, """import saliweb.build

vars = Variables('config.py')
env = saliweb.build.Environment(vars, ['conf/live.conf']%s)
Help(vars.GenerateHelpText(env))

env.InstallAdminTools()
env.InstallCGIScripts()

Export('env')
SConscript('python/%s/SConscript')
SConscript('lib/SConscript')
SConscript('txt/SConscript')
SConscript('test/SConscript')""" % (envmodule, self.short_name)

    def _make_sconscripts(self):
        f = open(os.path.join(self.topdir, 'python', self.short_name,
                              'SConscript'), 'w')
        print >> f, """Import('env')

env.InstallPython(['__init__.py'])"""

        f = open(os.path.join(self.topdir, 'lib', 'SConscript'), 'w')
        print >> f, """Import('env')

env.InstallPerl(['%s.pm'])""" % self.short_name

        f = open(os.path.join(self.topdir, 'txt', 'SConscript'), 'w')
        print >> f, """Import('env')

env.InstallTXT(['help.txt', 'contact.txt'])"""

        f = open(os.path.join(self.topdir, 'test', 'backend',
                              'SConscript'), 'w')
        print >> f, """Import('env')

env.RunPythonTests(Glob("*.py"))"""

        f = open(os.path.join(self.topdir, 'test', 'frontend',
                              'SConscript'), 'w')
        print >> f, """Import('env')

env.RunPerlTests(Glob("*.pl"))"""

        f = open(os.path.join(self.topdir, 'test',
                              'SConscript'), 'w')
        print >> f, """SConscript('backend/SConscript')
SConscript('frontend/SConscript')"""


    def _make_config(self):
        f = open(os.path.join(self.topdir, 'conf', 'live.conf'), 'w')
        print >> f, """[general]
admin_email: %(user)s@salilab.org
socket: %(install)s/%(short_name)s.socket
service_name: %(service_name)s
urltop: http://modbase.compbio.ucsf.edu/%(short_name)s

[backend]
user: %(short_name)s
state_file: %(install)s/server.state
check_minutes: 10

[database]
backend_config: backend.conf
frontend_config: frontend.conf
db: %(db)s

[directories]
install: %(install)s
incoming: %(install)s/incoming/
preprocessing: /netapp/sali/%(user)s/running/
completed: %(install)s/completed/
failed: %(install)s/failed/

[oldjobs]
archive: 7d
expire: 30d""" % self.__dict__
        for (end, user) in (('frontend', self.db_frontend_user),
                            ('backend', self.db_backend_user)):
            fname = os.path.join(self.topdir, 'conf', '%s.conf' % end)
            passwd = self._make_password(20)
            f = open(fname, 'w')
            print >> f, """[%s_db]
user: %s
passwd: %s""" % (end, user, passwd)
            f.close()
            os.chmod(fname, 0600)

    def _make_frontend(self):
        f = open(os.path.join(self.topdir, 'lib',
                              '%s.pm' % self.short_name), 'w')
        print >> f, """package %(short_name)s;
use base qw(saliweb::frontend);
use strict;

sub new {
    return saliweb::frontend::new(@_, @CONFIG@);
}

sub get_navigation_links {
    my $self = shift;
    my $q = $self->cgi;
    return [
        $q->a({-href=>$self->index_url}, "%(service_name)s Home"),
        $q->a({-href=>$self->queue_url}, "%(service_name)s Current queue"),
        $q->a({-href=>$self->help_url}, "%(service_name)s Help"),
        $q->a({-href=>$self->contact_url}, "%(service_name)s Contact")
        ];
}

sub get_project_menu {
    # TODO
}

sub get_footer {
    # TODO
}

sub get_index_page {
    # TODO
}

sub get_submit_page {
    # TODO
}

sub get_results_page {
    # TODO
}""" % self.__dict__

    def _make_backend(self):
        f = open(os.path.join(self.topdir, 'python', self.short_name,
                              '__init__.py'), 'w')
        print >> f, """import saliweb.backend

class Job(saliweb.backend.Job):

    def run(self):
        # TODO


def get_web_service(config_file):
    db = saliweb.backend.Database(Job)
    config = saliweb.backend.Config(config_file)
    return saliweb.backend.WebService(config, db)
"""

    def _make_txt(self):
        f = open(os.path.join(self.topdir, 'txt', 'contact.txt'), 'w')
        print >> f, """<p>Please address inquiries to:<br />
<script type="text/javascript">escramble('%s','salilab.org')</script></p>
""" % self.user

        f = open(os.path.join(self.topdir, 'txt', 'help.txt'), 'w')
        print >> f, "<h1>Help</h1>"


def get_options():
    parser = OptionParser()
    parser.set_usage("""
%prog [-h] SERVICE_NAME [SHORT_NAME]

Set up a directory structure for a new web service called "SERVICE_NAME".
"SERVICE_NAME" should be the human-readable name of the web service, for
example "ModFoo" or "Peptide Docking". It may contain spaces and mixed case.

"SHORT_NAME" should give a short name containing only lowercase letters and
no spaces. (If not given, it is generated from "SERVICE_NAME" by lowercasing
and replacing spaces with underscores.) This name is used to name the
directory containing the files, the generated Python and Perl modules,
system and MySQL users etc.

e.g.
%prog ModFoo
%prog "Peptide Docking" pepdock
""")
    opts, args = parser.parse_args()
    if len(args) < 1 or len(args) > 2:
        parser.error("Wrong number of arguments given")
    if len(args) == 2 and (' ' in args[1] or args[1].lower() != args[1]):
        parser.error("SHORT_NAME must be all lowercase and contain no spaces")
    return args

def main():
    args = get_options()
    m = MakeWebService(*args)
    m.make()

if __name__ == '__main__':
    main()
