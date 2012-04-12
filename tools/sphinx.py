# Simple Sphinx tool and builder.

import os
from SCons.Script import *

# Build sphinx documentation:
def _action_sphinx(target, source, env):
    sourcedir = os.path.dirname(source[0].path)
    outdir = os.path.dirname(target[0].path)
    app = "%s %s %s %s" % (env['SPHINX_BUILD'], env['SPHINX_OPTS'],
                           sourcedir, outdir)
    ret = env.Execute([app, 'tools/munge-sphinx-perl.pl'])
    if not ret:
        print "Build finished. The HTML pages are in " + outdir
    return ret

def generate(env):
    """Add builders and construction variables for the sphinx tool."""
    import SCons.Builder
    builder = SCons.Builder.Builder(action=_action_sphinx)
    # Use Unix 'install' rather than env.InstallAs(), due to scons bug #1751
    install = SCons.Builder.Builder(action="install -d ${TARGET.dir} && " + \
              "install -d ${TARGET.dir}/_static && " + \
              "install -d ${TARGET.dir}/_sources && " + \
              "install -d ${TARGET.dir}/modules && " + \
              "install -d ${TARGET.dir}/_sources/modules && " + \
              "install ${SOURCE.dir}/*.html ${TARGET.dir} && " + \
              "install ${SOURCE.dir}/*.js ${TARGET.dir} && " + \
              "install ${SOURCE.dir}/modules/*.html " + \
                       "${TARGET.dir}/modules && " + \
              "install ${SOURCE.dir}/_sources/*.txt " + \
                       "${TARGET.dir}/_sources && " + \
              "install ${SOURCE.dir}/_sources/modules/* " + \
                       "${TARGET.dir}/_sources/modules && " + \
              "install ${SOURCE.dir}/_static/* ${TARGET.dir}/_static")
    env.Append(BUILDERS = {'Sphinx': builder, 'SphinxInstall':install})

    env.AppendUnique(SPHINX_BUILD='/usr/bin/sphinx-build')
    env.AppendUnique(SPHINX_OPTS='-a -E -b html')

def exists(env):
    """Make sure sphinx tools exist."""
    return env.Detect("sphinx")
