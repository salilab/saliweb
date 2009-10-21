.. currentmodule:: saliweb.backend

Deploying the web service
*************************

To actually deploy the web service, it is necessary to package the Python
classes that implement the backend and the Perl classes that implement the
frontend, then use the build system to install these classes in the correct
location, together with other resources such as images, style sheets or
text files needed by the web interface.

Prerequisites
=============

Every service needs some basic setup:

* The service needs its own MySQL database, and two MySQL users set up, one for
  the backend and the other for the frontend. A sysadmin can set this up on
  the `modbase` machine.

* Generally speaking, the service needs its own user on the `modbase` machine;
  for example, there is a `modloop` user for the ModLoop service. It is this
  user that runs `scons` (below). All of the backend also runs as this user,
  and jobs on the SGE clusters also run under this user's account. It is
  generally not a good idea to use a regular user for this purpose, as it will
  use up the regular user's quota (disk and runtime) on the cluster, and bugs
  in the service could lead to deletion of that user's files or their exposure
  to outside attack. A sysadmin can also set up this user account.

* The web service user needs a directory on the NetApp disk in order to store
  running jobs, and at least one directory on a local `modbase` disk so the
  frontend can create incoming jobs.

* A sysadmin needs to configure the web server on `modbase` so that the
  ``html`` and ``cgi`` subdirectories of the directory the service is deployed
  into are visible to the outside world. They can also password protect the
  page if it is not yet ready for a full release.

* It is usually a good idea to put the implementation files for a web service
  in an SVN repository.

.. _backend_package:

Backend Python package
======================

The backend for the service should be implemented as a Python package in the
``python`` subdirectory. Its name should be the same as the service, except
that it should be all lowercase, and any spaces in the service name should be
replaced with underscores. For example, the 'ModFoo' web service should be
implemented by the file :file:`python/modfoo/__init__.py`).
This package should implement a :class:`Job` subclass and may also
optionally implement :class:`Database` or :class:`Config` subclasses. It should
also provide a function `get_web_service` which, given the name of a
configuration file, will instantiate a :class:`WebService` object, using these
custom subclasses, and return it.
This function will be used by utility scripts set up by the build system to
run and maintain the web service. An example, building on previous ones,
is shown below.

.. literalinclude:: ../examples/package.py
   :language: python

.. _frontend_module:

Frontend Perl module
====================

The frontend for the service should be implemented as a Perl module in the
``lib`` subdirectory, named as for the :ref:`backend <backend_module>` (e.g.
the 'ModFoo' web service's frontend should be implemented by the file
:file:`lib/modfoo.pm`).
An example is shown below. For clarity, only the methods are shown, not their
contents; for full implementations of the methods see the :ref:`frontend` page.

.. literalinclude:: ../examples/frontend-complete.pm
   :language: perl

Configuration file
==================

The service's configuration should be placed in a configuration file in the
``conf`` subdirectory. Multiple files can be created if desired, for example
to maintain both a testing and a live version of the service. Each
configuration file can specify a different install location, MySQL database,
etc. This directory will also contain the supplementary configuration files
that contain the usernames and passwords that the backend and frontend need
to access the MySQL database. Since these files contain sensitive information
(passwords), they should **not** be group- or world-readable
(`chmod 0600 backend.conf`), and if using SVN, **do not** put these database
configuration files into the repository. 

Using the build system
======================

The build system is a set of extensions to SCons that simplifies the
setup and installation of a web service. To use, create a directory in which
to develop the web service, and create a file *SConstruct* in that directory
similar to the following:

.. literalinclude:: ../examples/SConstruct.simple
   :language: python

This script creates an :class:`~saliweb.build.Environment` object which will set
up the web service using either the configuration file *live.conf* or the file
*test.conf* in the *conf* subdirectory.

The :class:`~saliweb.build.Environment` class derives from the standard SCons
Environment class, but adds additional methods which simplify the setup of
the web service. For example, the
:meth:`~saliweb.build.Environment.InstallAdminTools` method installs a set of
command-line admin tools in the web service's directory (see below).
*SConscript* files in subdirectories can use similar methods (such as
:meth:`~saliweb.build.Environment.InstallPerl` or
:meth:`~saliweb.build.Environment.InstallPython`) to set up the rest of the
necessary files for the web service.

To actually install the web service, run `scons build=live`
or `scons build=test` from the command line on the `modbase` machine, as the web
service backend user, to install using either of the two
configuration files listed in the example above. (If `scons` is run with no
arguments, it will use the first one, *live.conf*.) Before
actually installing any files, this will check to make sure things are set
up for the web service to work properly - for example, that the necessary
MySQL users and databases are present.

Command-line admin tools
========================

The build system creates several command-line admin tools in the *bin*
subdirectory under the web service's install directory. These can be run by
the web service user to control the service itself and manipulate jobs in
the system.

service.py
----------

This tool is used to start, stop or restart the backend itself for the
web service. This daemon performs all functions of the web service, waiting
for jobs submitted by the web frontend and submitting them to the cluster,
harvesting completed cluster jobs, and expiring old job results. The tool
also has a *condstart* option which will only start the service if it is not
already running. This can be used by a cronjob to make sure the service is
automatically restarted if it is terminated, for example by a reboot of the
modbase machine.

resubmit.py
-----------

This tool will move a single job from the **FAILED** state back to the
**INCOMING** state. It is designed to be used to resubmit failed jobs once
whatever problem with the web service that caused these jobs to fail the
first time around has been resolved.

deljob.py
---------

This tool will delete a single job in a given state. It can be used to remove
failed jobs from the system, or to purge information from the database on
expired jobs. Jobs in other states (such as **RUNNING** or **COMPLETED**) can
also be deleted, but only if the backend service is stopped first, since that
service actively manages jobs in these states.

.. _complete_examples:

Examples
========

A simple example of a complete web service is ModLoop. The source code for
this service can be found at
https://svn.salilab.org/modloop/branches/new-framework/
and the service can be seen in action at
http://modbase.compbio.ucsf.edu/modloop-test/
