"""Utility functions used by all IMP modules"""

import os.path
import re
import sys
from SCons.Script import *

__all__ = ["add_common_variables", "MyEnvironment"]

class WineEnvironment(Environment):
    """Environment to build Windows binaries under Linux, by running the
       MSVC compiler (cl) and linker (link) through wine, using the w32cc
       and w32link shell scripts"""
    def __init__(self, platform='win32', CC='w32cc', LINK='w32link', **kw):
        if sys.platform != 'linux2':
            print "ERROR: Wine is supported only on Linux systems"
            Exit(1)
        Environment.__init__(self, platform=platform, CC=CC, LINK=LINK, **kw)
        posix_env = Environment(platform='posix')
        self['SHLIBPREFIX'] = self['LIBLINKPREFIX'] = 'lib'
        self['WINDOWSEXPPREFIX'] = 'lib'
        self['LIBSUFFIX'] = '.lib'
        self['PSPAWN'] = posix_env['PSPAWN']
        self['SPAWN'] = posix_env['SPAWN']
        self['SHELL'] = posix_env['SHELL']
        self['ENV'] = posix_env['ENV']
        self['PYTHON'] = 'w32python'
        self['PATHSEP'] = ';'
        # Use / rather than \ path separator:
        self['LINKCOM'] = self['LINKCOM'].replace('.windows', '')
        # Make sure we get the same Windows C/C++ library as Modeller, and
        # enable C++ exception handling
        self.Append(CFLAGS="/MD")
        self.Append(CXXFLAGS="/MD /GR /GX")

def MyEnvironment(variables=None, *args, **kw):
    """Create an environment suitable for building"""
    # First make a dummy environment in order to evaluate all variables, since
    # env['wine'] will tell us which 'real' environment to create:
    env = Environment(tools=[], variables=variables)
    if env['wine']:
        env = WineEnvironment(variables=variables, *args, **kw)
    else:
        env = Environment(variables=variables, *args, **kw)
        env['PYTHON'] = 'python'
        env['PATHSEP'] = os.path.pathsep
    return env

def add_common_variables(vars, package):
    """Add common variables to an SCons Variables object."""
    vars.Add(PathVariable('prefix', 'Top-level installation directory', '/usr',
                          PathVariable.PathAccept))
    vars.Add(PathVariable('bindir', 'Binary installation directory',
                          '${prefix}/bin', PathVariable.PathAccept))
    vars.Add(PathVariable('pythondir', 'Python module installation directory',
                          '${prefix}/lib/python%d.%d/site-packages' \
                          % sys.version_info[0:2], PathVariable.PathAccept))
    vars.Add(PathVariable('perldir', 'Perl module installation directory',
                          '${prefix}/lib64/perl5/vendor_perl',
                          PathVariable.PathAccept))
    vars.Add(PathVariable('docdir', 'Documentation installation directory',
                          '${prefix}/share/doc/%s' % package,
                          PathVariable.PathAccept))
    vars.Add(PathVariable('webdir', 'Web data file installation directory',
                          '/var/www/html/saliweb', PathVariable.PathAccept))
    vars.Add(BoolVariable('wine',
                          'Build using MS Windows tools via Wine emulation',
                          False))
    vars.Add('http_proxy', 'Proxy for sphinx to use to get Python doc links')
    vars.Add('https_proxy',
             'Proxy for sphinx to use to get SSL Python doc links')
    vars.Add(BoolVariable('coverage',
                          'Get coverage information from tests',
                          True))
