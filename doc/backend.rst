.. currentmodule:: saliweb.backend

.. _backend:

Backend
*******

The backend is a set of Python classes that manages jobs after the
initial submission. This typically runs from a cronjob on our 'modbase'
machine, picking up submitted jobs from the frontend, submitting jobs
to the cluster and gathering results, and doing any necessary pre- or
post-processing.

The backend is implemented by the :mod:`saliweb.backend` Python module.


Classes
=======

Job
---

The :class:`Job` class represents a single job known to the backend. This
can be job just submitted by the frontend, it can be running on the cluster,
it could have finished and its results placed on long-term storage, or the
results from a very old job could have been deleted (only the job metadata
remains). Each job corresponds to a single row in the jobs database table
and a directory on disk.

For any web service, the :class:`Job` class must first be subclassed and then
one or more of its methods implemented to actually do the work of running jobs.
For example, the :meth:`Job.run` method will be called by the backend when
the job starts; it is expected to start the job running on the cluster,
typically by using an :class:`SGERunner` object. There are similar methods
that can be used to do extra processing before the job starts
(:meth:`Job.preprocess`), after it finishes running on the cluster
(:meth:`Job.postprocess`) or when the job is moved to long-term storage
(:meth:`Job.archive`), for example. Each method is run in the directory
containing all of the job's data (i.e. any files uploaded by the end user
when the job was submitted, plus any output files after the job has run).
If any of these methods raises an exception, it is caught by the backend;
the job is put into a failed state and the server admin is notified. Thus,
exceptions should be used only to indicate a technical error in the web
service, not something wrong with the user's input (in the latter case, the
job output should simply indicate what the problem is).

As mentioned above, an :class:`SGERunner` class is provided that takes care of
the details of running a script on the cluster and checking if it has
completed. Typically the script run here should use the local /scratch disk
on the cluster nodes if possible - this is not implemented automatically by
the framework, since the best usage of local and network disks is specific
to a given web service.


Database
--------

Each job's metadata is stored in a database; the :class:`Database` class
manages this database and creates :class:`Job` objects automatically when
requested to by other classes. The base :class:`Database` class interfaces
with a MySQL database on the 'modbase' machine and manages database tables
containing fields used by all web services. It can be subclassed to add
additional fields (for example, to store some extra job metadata in the
database rather than within the job's directory) or (potentially) to use a
different database engine.


Config
------

The :class:`Config` class parses the configuration file for the web service
and stores all of the configuration information. It can be subclassed if
desired to read extra service-specific information from the configuration file.


WebService
----------

The :class:`WebService` class provides high-level backend functionality.
It provides simple methods to process pending jobs (e.g.
:meth:`WebService.process_completed_jobs`, which looks at all jobs currently
running on the cluster and, for each one that has completed, processes the
job and collects the results). It is rarely necessary to subclass.
