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
(The exception is :meth:`Job.expire`, which is called after the job directory
has been deleted.)
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

.. _jobstates:

Job states
==========

A single job in the system is represented by a row in the database table
and a single directory that contains the job inputs and/or outputs. Each job
can be in one of a set of distinct states, described below. In normal operation
a job will move from the first state in the list below to the last.

* The **INCOMING** state is for jobs that have just been submitted to the
  system by the frontend, but not yet picked up by the frontend.

* Jobs move into the **PREPROCESSING** state when they are picked up by the
  frontend. At this point the :meth:`Job.preprocess` method is called, which
  can be overridden to do any necessary preprocessing. Note that this method
  runs on the server machine ('modbase') and serially (for only a single job
  at a time), so it should not run any calculations that take more than a few
  seconds.

* Next, jobs usually move to the **RUNNING** state. At this point the
  :meth:`Job.run` method is called, which typically will submit an SGE
  job to do the bulk of the processing.

* When the SGE job finishes, the job moves to the **POSTPROCESSING** state and
  the :meth:`Job.postprocess` method is called. Like preprocessing, this runs
  serially on the server machine and so should not be computationally
  expensive.

* Next the job moves to the **COMPLETED** state and the :meth:`Job.complete`
  method is called. If the user provided an email address to the frontend,
  they are emailed at this point to let them know job results are now
  available.

* After a defined period of time, the job moves to the **ARCHIVED** state
  and the :meth:`Job.archive` method is called. At this point the job results
  are still present on disk, but are no longer accessible to the end user and
  may be moved to long-term storage.

* After another defined period of time, the job moves to the **EXPIRED** state,
  the job directory is deleted, and the :meth:`Job.expire` method is called.
  At this point, only the job metadata in the database remains.

If a problem is encountered at any point (such as a Python exception) the job
is moved to the **FAILED** state. At this point the server admin is emailed
and is expected to fix the problem (usually a bug in the web service, or a
system problem such as a broken or full hard disk).

Note also the :meth:`Job.preprocess` method can, if desired, signal to the
framework that running a full SGE job is unnecessary. In this case, the
**RUNNING** and **POSTPROCESSING** steps are skipped and the job moves
directly from **PREPROCESSING** to **COMPLETED**.

Each job state (with the exception of **EXPIRED**) can be given a directory
in the service's configuration file. Job data are automatically moved between
directories when the state changes. For example, the **INCOMING** directory
generally needs to reside on a local disk, and have special permissions so that
the frontend can create files within it. The **RUNNING** directory usually
needs to be accessible by the cluster, so it needs to be on the NetApp disk.
The **ARCHIVED** directory may live on long-term storage, such as a park disk.


Examples
========

Simple job
----------

The example below demonstrates a simple :class:`Job` subclass that, given a
set of PDB files from the frontend, runs an SGE job on the cluster that
extracts all of the HETATM records from each PDB. This is done by
overriding the :meth:`Job.run` method to pass a set of shell script commands
to an :class:`SGERunner` instance; this instance is then returned to the
backend. The backend will then keep track of the SGE job, and notice when
it finishes.

The subclass also overrides the :meth:`Job.archive` method, so that when the
job results are moved from short-term to long-term storage, all of the PDB
files are compressed with gzip to save space.

.. literalinclude:: ../examples/simplejob.py
   :language: python


Custom database class
---------------------

The :class:`Database` class can be customized by adding additional fields to
the database table. This is useful if you need to pass small amounts of job
metadata between the frontend and backend, or between different stages of the
job, and the metadata are useful to keep after the job has finished.

.. note:: In many cases, it makes more sense to store job data as files in the
          job directory itself. For example, it is probably easier to store
          a PDB file as a real file rather than trying to insert the
          contents into the database table!

This example adds a new integer field *number_of_pdbs* to the database. The
field can then be accessed (read or write) from within the :class:`Job` object
by referencing *self._metadata['number_of_pdbs']*. The *_metadata* attribute
stores all of the job metadata in a Python dictionary-like object; it is
essentially a dump of the database row corresponding to the job.

.. literalinclude:: ../examples/customdb.py
   :language: python
