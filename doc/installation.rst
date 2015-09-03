Installation
************

.. _install_lab:

In the Sali lab
===============

There is no need for most users to install the web framework. It is already
installed for you by our sysadmins on the 'modbase' server machine.

Sysadmins: if you do need to make modifications to the framework itself,
this can be done by cloning the `git repository <https://github.com/salilab/saliweb>`_
to a directory on modbase, making your
changes, writing test cases to exercise those changes, running 'scons test'
to make sure the changes didn't break anything, 'git commit' and 'git push'
to commit the changes, then running 'sudo scons install' to update the
installed version of the framework.

.. _outside_lab:

Outside of the Sali lab
=======================

The framework is designed to work in the Sali lab environment, but can be
used in other environments with some modification.

Prerequisites
-------------

* Python. The backend of the framework, which takes care of running jobs, is implemented in Python. It requires Python 2.6 or
  2.7 (it is not tested with Python 3).

* Perl. The frontend, which handles user submission of jobs and the display of results, is implemented in Perl, and uses a
  number of Perl modules, most notably CGI and DBI.

* SGE. The framework expects to be run on a machine that is a submit host to a Sun GridEngine compute cluster
  (or a compatible product, such as `OGE <http://www.oracle.com/us/products/tools/oracle-grid-engine-075549.html>`_
  or `OGS <http://gridscheduler.sourceforge.net/>`_). The framework talks to SGE via DRMAA, so you will also need
  the `DRMAA Python bindings <https://github.com/pygridtools/drmaa-python>`_. The framework contains classes to
  talk to the two SGE installations available in the Sali lab - :class:`SGERunner` and :class:`SaliSGERunner`
  in :file:`saliweb/python/saliweb/backend/__init__.py`. To work in your environment, add a new subclass to that file
  (see the implementation of :class:`SaliSGERunner` for an example) setting the `SGE_CELL` and `SGE_ROOT` environment
  variables appropriately, setting `DRMAA_LIBRARY_PATH` to the location of your :file:`libdrmaa.so` file, setting
  `_runner_name` to a unique value, and setting `_qstat` to the full path to your :file:`qstat` binary.

* `MODELLER <http://salilab.org/modeller/>`_. The framework needs your academic MODELLER license key (in order for
  the `check_modeller_key() function <http://salilab.org/saliweb/modules/frontend.html#saliweb::frontend.check_modeller_key>`_
  to work). It obtains this by parsing the :file:`config.py` file in your MODELLER installation. The framework is hardcoded
  to use the path of the Sali lab's own installation; to use outside of the Sali lab you will need to edit
  :file:`perl/saliweb/SConscript` and change the path to :file:`config.py`.

* Web server. The frontend consists of Perl CGI scripts which need to be hosted by a web server. Apache is used in the
  Sali lab, but other web servers would probably work too (the only assumption made in the code is that files uploaded
  to the web server end up owned by the `httpd` user, but this would be easy to change). The web server does not have
  to run on the same machine as the framework, but it does need access to the same filesystems (see below).

* MySQL database. Both the frontend and backend need access to a MySQL database in which the jobs are stored. This requires
  the Perl DBI and DBD-MySQL packages, plus the Python MySQLdb package. The framework itself needs no special access to the
  database, but each web service that uses the framework needs its own database. (The MySQL server can reside on a different
  machine to the framework if desired.)
  
* Unix user. Each web service that uses the framework runs under its own user ID, and the jobs are run on the SGE cluster
  using the same ID. Thus, generally admin access to the cluster is required to add these users.

* Filesystems. Each web service that uses the framework needs access to a local filesystem on the SGE submit host. This will
  be used by the web server to deposit newly-submitted jobs (the 'incoming' directory). The filesystem needs to support
  `POSIX ACLs <http://www.vanemery.com/Linux/ACL/POSIX_ACL_on_Linux.html>`_ (this generally rules out NFS) since the directory
  will be owned by a Unix user unique to that web service, but will have a POSIX ACL applied to allow the Apache httpd user
  to write files into it. Each web service will also need a directory on a shared volume, visible to the cluster nodes,
  where the files for jobs that run on the cluster are placed (the 'running' directory). (If space is limited on the network
  storage, web services can also be configured to move the files back to the cheaper local filesystem - the 'completed'
  directory - when the job is done.)
