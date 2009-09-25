.. currentmodule:: saliweb.backend

Deploying the web service
*************************

To actually deploy the web service, you should package your Python classes that
implement the backend, then use the build system to install these classes in
the correct location, together with the web pages, CGI scripts and other files
that constitute the frontend.

Python package
==============

Your web service should be designed as a Python package (i.e. the
'foo' web service should be implemented by the file foo/__init__.py).
This package should implement a :class:`Job` subclass and may also
optionally implement :class:`Database` or :class:`Config` subclasses. It should
also provide a function `get_web_service` which, given the name of a
configuration file, will instantiate a :class:`WebService` object and return it.
This function will be used by utility scripts set up by the build system to
run and maintain the web service. An example, building on previous ones,
is shown below.

.. literalinclude:: ../examples/package.py
   :language: python

Using the build system
======================

The build system is a set of extensions to SCons that simplifies the
setup and installation of a web service. To use, create a directory in which
to develop your web service, and create a file *SConstruct* in that directory
similar to the following:

.. literalinclude:: ../examples/SConstruct.simple
   :language: python

This example will set up the web service using either the configuration file
*live.conf* or the file *test.conf* in the *conf* subdirectory. Each
configuration file can specify a different install location, MySQL database,
etc. (only one configuration file is required). To install, run `scons live`
or `scons test` from the command line (or just `scons` to install the first
one, *live.conf*).

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

.. _complete_service:

A complete web service
======================

A complete web service is built up using the frontend, backend, and build
system. A simple example of such a complete webservice is ModLoop,
which can be found at
https://svn.salilab.org/modloop/branches/new-framework/
