.. currentmodule:: saliweb.backend

.. _configfile:

Configuration file
******************

The example file below defines the configuration for a fictional 'ModFoo'
service:

.. literalinclude:: ../examples/example.conf

The configuration file is used to store information used by the
:ref:`backend <backend>`, the
frontend, and the build system. It is a fairly standard 'INI' file, containing
section titles in square brackets (e.g. [general]) and key-value pairs within
the sections, either of the form 'foo: bar' or 'foo = bar'.

Each section in the configuration file is described below.

general
=======

admin_email
    The email address of the administrator of this web service. This is used
    to notify the admin if a job fails with a technical error or the entire
    web service encounters an unrecoverable error and cannot continue.

state_file
    The full path to a file that is used by the backend to store state
    between calls. In normal operation this is simply used as a lock file to
    ensure that only one copy of the backend is running at a time. After an
    unrecoverable error, this file continues information on the nature of the
    failure and must be manually removed by the admin before the backend will
    run again.

socket
    The full path to a socket file that is used for the frontend to send
    messages to the backend.

check_minutes
    The backend checks periodically to see if the batch system (e.g. SGE)
    reports that any running jobs have finished, and to see if any jobs have
    been submitted by the frontend. This is the time, in minutes, to wait
    between these queries. A longer time reduces the load on the cluster
    servers but increases the apparent time a job takes to run. Archived and
    expired jobs are also checked for periodically, but this interval is
    fixed at 10% of the shorter of the archive and expiry times.

service_name
    The name of the service. This is used in emails to the owners of jobs and
    the server admin, and by the build system.

urltop
    The URL under which the service's web pages live. This is used to construct
    URLs containing job results, for example.

database
========

db
    The name of the database in which the service's data are stored.

backend_config, frontend_config
    Filenames of additional INI files containing the MySQL username and
    password used by the backend and frontend to communicate with the database
    (in sections called [backend_db] and [frontend_db] respectively).
    (The frontend and backend should use different MySQL users, since they
    should have different access rights set up for the job tables.)
    If these filenames are not absolute paths, they are taken to be relative
    to the directory containing the main configuration file. The database
    authentication information has to stored in separate files so that file
    permissions can be set appropriately so that the frontend cannot read the
    backend configuration. An example backend.conf is shown below.

.. literalinclude:: ../examples/backend.conf

directories
===========

install
    The top-level directory in which the web service files are installed.

incoming, preprocessing, etc.
    Each :ref:`job state <jobstates>` except EXPIRED can be given a directory
    in which the job data are placed. Only the INCOMING and PREPROCESSING
    directories are required; others, if not specified, will default to the
    same as the PREPROCESSING directory.

oldjobs
=======

This section controls what happens to old jobs after they have completed.

archive
    Completed job results, after this time, will no longer be available for
    the end user to download from the frontend. The time is either NEVER to
    indicate that job results are available forever, or a number with a
    single character suffix (h for hours, d for days, m for months or y for
    years). For example, '90d' will archive job results after 90 days.

expire
    Completed job results will be deleted from disk after this time. Times are
    specified in the same way as for *archive*. Note that the *archive* time
    cannot be longer than the *expire* time.
