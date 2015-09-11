.. currentmodule:: saliweb.backend

.. _build_system:

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

* The service needs its own user on the `modbase` machine;
  for example, there is a `modloop` user for the ModLoop service. It is this
  user that runs `scons` (below). All of the backend also runs as this user,
  and jobs on the SGE clusters also run under this user's account. (It is
  not a good idea to use a regular user for this purpose, as it will
  use up the regular user's disk and runtime quota on the cluster, and bugs
  in the service could lead to deletion of that user's files or their exposure
  to outside attack.) A sysadmin can also set up this user account.

* The web service user needs a directory on the NetApp disk in order to store
  running jobs, and at least one directory on a local `modbase` disk so the
  frontend can create incoming jobs.

* A sysadmin needs to configure the web server on `modbase` so that the
  ``html`` and ``cgi`` subdirectories of the directory the service is deployed
  into are visible to the outside world. They can also password protect the
  page if it is not yet ready for a full release.

* It is usually a good idea to put the implementation files for a web service
  on GitHub, or in an SVN repository.

.. _quick_start:

Quick start
===========

The easiest way to set up a new web service is to simply run the
``make_web_service`` script on the `modbase` machine. Given the name of the
web service it will set up all the necessary
files used for a basic web service. Run ``make_web_service`` with no
arguments for further help.

.. note::
   ``make_web_service`` should be run on a local disk (**not** /netapp). Most
   users on `modbase` have their home directories on a local disk, so this is
   generally OK by default. Note that the home directory should be accessible
   by the backend user in order for the build system to work; running
   ``chmod a+rx ~`` should usually be sufficient.

Example usage
-------------

For example, the user 'bob' wants to set up a web service for peptide docking.

 #. He first chooses a "human readable" name for his service, "Peptide Docking".
    This name will appear on web pages and in emails, but can be changed
    later by editing the configuration file, if desired.

 #. He also chooses a "short name" for his service, "pepdock". The short name
    should be a single lowercase word; it is used to name system and MySQL
    users, the Perl and Python modules, etc. It is difficult to change later,
    but is never seen by end users so is essentially arbitrary.

 #. He asks a sysadmin to set up the web service, giving him or her the
    "short name" and the human readable name. (The sysadmin will run the
    `make_web_service` script.)

 #. Bob can then get the web service from Subversion by running::

     $ svn co https://svn.salilab.org/pepdock/trunk pepdock
     $ cd pepdock/conf
     $ sudo -u pepdock cat ~pepdock/service/conf/backend.conf > backend.conf
     $ sudo -u pepdock cat ~pepdock/service/conf/frontend.conf > frontend.conf

 #. Bob edits the :ref:`configuration file <configfile>`
    in :file:`conf/live.conf` to adjust install locations, etc. if necessary,
    and fills in the template Python and Perl modules for the
    :ref:`backend <backend>` and :ref:`frontend <frontend>`, in
    :file:`python/pepdock/__init__.py` and :file:`lib/pepdock.pm`, respectively.

 #. He writes test cases for both the frontend and backend (see :ref:`testing`)
    and runs them to make sure they work by typing `scons test` in the pepdock
    directory.

 #. He deploys the web service by simply typing `scons` in the pepdock
    directory. This will give him further instructions to complete the setup
    (for example, providing a set of MySQL commands to give to a sysadmin to
    set up the database).

 #. Once deployment is successful, he asks a sysadmin to set up the web server
    on `modbase` so that the URL given in `urltop` in :file:`conf/live.conf`
    works, and to register the service with 
    `Google Analytics <https://salilab.org/internal/wiki/GoogleAnalytics>`_.
    The resulting UA number should also get entered into the configuration file.

 #. Whenever Bob makes changes to the service in his `pepdock` directory, he
    simply runs `scons test` to make sure the changes didn't break anything,
    then `scons` to update the live copy of the service, then `svn up` and
    `svn ci` to store his changes in the Subversion repository.
    (The backend will also need to restarted when he does this, but `scons`
    will show a suitable command line to achieve this.)

 #. If Bob wants to share development of the service with another user, Joe,
    they should ask a sysadmin to give Joe `sudo` access to the `pepdock`
    account. Joe can then set up his own `pepdock` directory by checking out
    from Subversion and then developing in the same way as Bob, above.

.. note::
   Development of the service should generally be done by the regular ('bob')
   user; only the backend itself runs as the backend ('pepdock') user. Bob can
   however run any command as the 'pepdock' user using 'sudo'
   (e.g. ``sudo -u pepdock scons`` to run scons as the pepdock user). Note that
   sudo will ask for the regular user's (Bob's) password, not the pepdock
   account (which does not have a password anyway, and cannot be logged into).
   For advanced access, a shell can be opened as the backend user by running
   something like ``sudo -u pepdock bash``.

The following sections describe the various components of a web service in more
detail, for developers that wish to set things up themselves without using the
convenience scripts.

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

.. _deploy_config:

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
(`chmod 0600 backend.conf`), and if using SVN or git, **do not** put
these database configuration files into the repository.

.. _deploy_build:

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

To test the web service, run `scons test` from the command line on the
`modbase` machine (see :ref:`testing`).

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
already running (the regular *start* option will complain if the service is
running).

resubmit.py
-----------

This tool will move one or more jobs from the **FAILED** state back to the
**INCOMING** state. It is designed to be used to resubmit failed jobs once
whatever problem with the web service that caused these jobs to fail the
first time around has been resolved.

deljob.py
---------

This tool will delete one or more jobs in a given state. It can be used to
remove failed jobs from the system, or to purge information from the database on
expired jobs. Jobs in other states (such as **RUNNING** or **COMPLETED**) can
also be deleted, but only if the backend service is stopped first, since that
service actively manages jobs in these states.

failjob.py
----------

This tool will force one or more jobs into the **FAILED** state. This is useful
if, for example, due to a bug in the backend, a job didn't work properly but
went into the **COMPLETED** state. The backend service must first be
stopped in order to use this tool.

delete_all_jobs.py
------------------

This tool will delete all of the jobs from the web service, so can be used to
'restore to factory settings'. It deletes the database table, and all the files
in all the job directories (even extraneous files that do not correspond to
jobs in the database). It should be used with caution, as this cannot be undone.

list_jobs.py
------------

This tool will show all the jobs in the given state(s). It is helpful for
internal web services that don't have an easily accessible queue web page.

.. _testing:

Testing
=======

Before the framework is put into production it should be tested to make sure
it works correctly. There are two main types of tests that should be done:

* **Unit tests** test individual parts of the service to make sure they work
  in isolation.

* **System tests** test the service as a whole.

Unit tests
----------

To test the frontend, make a `test/frontend` subdirectory and put one or more
Perl scripts there. Each script can use the :class:`saliwebTest` class,
and its :meth:`~saliwebTest.make_frontend` method, to create simple instances
of the web frontend and test various methods given different inputs, using
the standard Perl `Test::More` and `Test::Exception` modules. For example,
a script to test the :meth:`~saliwebfrontend.get_navigation_links` method might
look like:

.. literalinclude:: ../examples/test-navigation.pl
   :language: perl

Then write an SConscript file in the same directory to actually run the
scripts, using the :meth:`~saliweb.build.Environment.RunPerlTests`
method. This might look like:

.. literalinclude:: ../examples/SConscript-frontend-test
   :language: python

To test the backend, make a `test/backend` subdirectory and put one or more
Python scripts there. Each script should define a subclass of
:class:`saliweb.test.TestCase` and define one or methods starting with *test_*
using standard Python *unittest* methods such as *assertEquals*. A number of
other utility classes are also provided in the :mod:`saliweb.test` module.

For example, to test that the :meth:`~saliweb.backend.Job.archive` method of
the ModFoo service (:ref:`simplejob` example) really does gzip all of the PDB
files, a test case like that below could be used:

.. literalinclude:: ../examples/test-archive.py
   :language: python

Then write an SConscript file in the same directory to actually run the
scripts, using the :meth:`~saliweb.build.Environment.RunPythonTests`
method. This might look like:

.. literalinclude:: ../examples/SConscript-backend-test
   :language: python

Run `scons test` to actually run the tests.

System tests
------------

There is currently no rigorous way to carry out system tests other than
:ref:`deploying the service <quick_start>`,
providing an implementation for the :meth:`~saliwebfrontend.get_submit_page`
frontend method, then using the web interface or runnning the `cgi/submit.cgi`
script (in the web service's installation directory, as the backend user) to
submit a job.

.. _complete_examples:

Examples
========

A simple example of a complete web service is ModLoop. The source code for
this service can be found at
https://github.com/salilab/modloop/
and the service can be seen in action at
http://salilab.org/modloop/
