.. highlight:: rest

The :mod:`saliweb.build` Python module
======================================

.. module:: saliweb.build
   :synopsis: Simple SCons-based build infrastructure for web services.

This module provides a simple SCons-based build infrastructure for web services.

.. class:: Environment(variables, configfiles[, version[, service_module]])

   A simple class based on the standard SCons Environment class. This class
   should be instantiated in the top-level SConstruct file of a web service,
   and will check the configuration and install basic files. It must be given
   a set of SCons Variables, and the name of one or more configuration
   files. The user will be able to choose which configuration to build with
   by specifying the `build` option on the command line; if the user does not
   give this option, the first configuration file in *configfiles* is used.
   If *version* is specified, it should be a string specifying the version
   number of the service (e.g. "1.0.0"). If it is not, it is assumed that
   the web service is being deployed from an SVN checkout, and the
   ``svnversion`` program is run to attempt to determine the version number.

   If *service_module* is specified, it is the name of the Python and Perl
   modules used to implement the service (it must be lowercase and contain
   no spaces). If not given, it is generated automatically from the service
   name in the configuration file (the name is lowercased and spaces are
   replaced with underscores).

   .. method:: InstallAdminTools([tools])

      Installs command-line admin tools in the ``bin`` directory underneath the
      installation directory. *tools* is a list of names to install that
      must be selected from the convenience modules provided by the
      :mod:`saliweb.backend` package, such as `resubmit` or `service`.
      If *tools* is not specified, all tools are installed.

   .. method:: InstallCGIScripts([scripts])

      Installs CGI scripts that control the frontend, in the ``cgi``
      directory underneath the
      installation directory. *scripts* is a list of names to install that
      must be selected from the various display_*_page() methods implemented
      by the :class:`saliweb::frontend` class, such as `index.cgi` or
      `submit.cgi`. If *scripts* is not specified, all scripts are installed.

   .. method:: InstallPython(files[, subdir])

      Installs a provided list of Python files in the ``python`` directory
      underneath the installation directory. If installing subpackages, also
      specify the *subdir* argument to install them in a subdirectory.

   .. method:: InstallHTML(files[, subdir])

      Installs a provided list of HTML files in the ``html`` directory
      underneath the installation directory. The files can be installed in
      a subdirectory if desired by giving the *subdir* argument.

   .. method:: InstallCGI(files[, subdir])

      Installs a provided list of CGI scripts in the ``cgi`` directory
      underneath the installation directory. The files can be installed in
      a subdirectory if desired by giving the *subdir* argument. This is only
      required if you need to install additional CGI scripts; in most cases,
      the :meth:`InstallCGIScripts` method installs all the needed scripts.

   .. method:: InstallPerl(files[, subdir])

      Installs a provided list of Perl modules in the ``lib`` directory
      underneath the installation directory. The files can be installed in
      a subdirectory if desired by giving the *subdir* argument.

   .. method:: InstallTXT(files[, subdir])

      Installs a provided list of text files in the ``txt`` directory
      underneath the installation directory. The files can be installed in
      a subdirectory if desired by giving the *subdir* argument.

   .. method:: RunPerlTests(tests)

      Runs a set of Perl tests of the frontend implementation.

   .. method:: RunPythonTests(tests)

      Runs a set of Python tests of the backend implementation.

   .. class:: Frontend(name)

      This class is used to install an alternate frontend called *name*.
      There must be a corresponding section in the configuration file, and
      a Perl module, for this frontend (for example, a frontend called ``foo``
      needs a section in the configuration file called ``[frontend:foo]``
      and a Perl module (installed with :meth:`Environment.InstallPerl`)
      called ``foo.pm``). Methods are provided to install files for the
      frontend. They function identically to the methods in the
      :class:`Environment` class, but install the files in a subdirectory
      of the web service called *name*.

      .. method:: InstallHTML(files[, subdir])
      .. method:: InstallTXT(files[, subdir])
      .. method:: InstallCGIScripts([scripts])
