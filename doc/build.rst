.. highlight:: rest

The :mod:`saliweb.build` Python module
======================================

.. module:: saliweb.build
   :synopsis: Simple SCons-based build infrastructure for web services.

This module provides a simple SCons-based build infrastructure for web services.

.. class:: Environment(configfile[, service_name])

   A simple class based on the standard SCons Environment class. This class
   should be instantiated in the top-level SConstruct file of a web service,
   and will check the configuration and install basic files. It must be given
   the name of a configuration file, *configfile*. It will also need to know
   the name of the Python package that implements the web service;
   this is provided by the *service_name* parameter. If this is not given,
   the Python package name is assumed to be match the service_name parameter
   in the configuration file, after it is converted to lower case.

   .. method:: InstallBinaries([binaries])

      Installs convenience binaries in the ``bin`` directory underneath the
      installation directory. *binaries* is a list of names to install that
      must be selected from the convenience modules provided by the
      :mod:`saliweb.backend` package, such as `resubmit` or `process_jobs`.
      If *binaries* is not specified, all binaries are installed.

   .. method:: InstallPython(files[, subdir])

      Installs a provided list of Python files in the ``python`` directory
      underneath the installation directory. If installing subpackages, also
      specify the *subdir* argument to install them in a subdirectory.
