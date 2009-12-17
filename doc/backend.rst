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
could have just been submitted by the frontend, it could be running on the
cluster, it could have finished and its results placed on long-term storage,
or the results from a very old job could have been deleted (only the job
metadata remains). Each job corresponds to a single row in the jobs database
table and a directory on disk.

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

.. note:: Each of these methods is automatically run by the backend at the
          correct time; they should not be run manually by any method
          in the subclass. For example, to run a new job, call
          :meth:`Job.reschedule_run`, not the :meth:`Job.run` method directly.

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
The most commonly-used method is :meth:`WebService.do_all_processing`, which
simply runs in an endless loop, submitting new jobs to the cluster, collecting
the results of finished jobs, and archiving old completed jobs.
It is rarely necessary to subclass.

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

If a problem is encountered at any point (usually a Python exception) the job
is moved to the **FAILED** state. At this point the server admin is emailed
and is expected to fix the problem (usually a bug in the web service, or a
system problem such as a broken or full hard disk).

Note also the :meth:`Job.preprocess` method can, if desired, signal to the
framework that running a full SGE job is unnecessary (by calling the
:meth:`Job.skip_run` method). In this case, the **RUNNING** and
**POSTPROCESSING** steps are skipped and the job moves directly from
**PREPROCESSING** to **COMPLETED**.  Similarly, the :meth:`Job.postprocess`
method can request that the framework runs a new job (by calling the
:meth:`Job.reschedule_run` method). In this case, the job moves from
**POSTPROCESSING** back to **RUNNING**.

Each job state (with the exception of **EXPIRED**) can be given a directory
in the service's configuration file. Job data are automatically moved between
directories when the state changes. For example, the **INCOMING** directory
generally needs to reside on a local disk, and have special permissions so that
the frontend can create files within it. The **RUNNING** directory usually
needs to be accessible by the cluster, so it needs to be on the NetApp disk.
The **ARCHIVED** directory may live on long-term storage, such as a park disk.


Examples
========

.. _simplejob:

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

Logging
=======

It is often useful for debugging purposes to log progress of a job. While the
job is running on the cluster, the only way to do this is to write output into
a log file. For other steps in the processing, however, the standard Python
`logging module <http://www.python.org/doc/2.3.5/lib/module-logging.html>`_
is utilized. Each job method (such as :meth:`Job.run`, :meth:`Job.preprocess`)
with the exception of :meth:`Job.expire` can use the :attr:`Job.logger` object
to write out log messages. It is a standard Python Logger object, so supports
the regular methods of a Logger, such as :meth:`~Logger.warning` and
:meth:`~Logger.critical` to write log messages, and :meth:`~Logger.setLevel`
to set the threshold for log output.

By default, anything logged that exceeds the threshold will be written to a file
called 'framework.log' in the job's directory. The file will only be created
when the first log message is printed. This behavior can be modified if desired
by overriding the :meth:`Job.get_log_handler` method.

.. literalinclude:: ../examples/logging.py
   :language: python

Testing
=======

The best way to test the backend is as part of the entire web service
(see :ref:`testing`).

However, the backend can be tested directly without invoking the frontend, by
manually modifying the MySQL database. Note, however, that the interface
between the backend and frontend, as well as the details of the MySQL tables,
are not guaranteed to be stable (future iterations of the framework may change
some of the details for performance or additional features), so this method
could fail in future.

To manually submit a job:

 #. Decide on a job name. This must be unique. Create a directory with the same
    name, as the backend user, under the web service's incoming directory
    (as specified in the configuration file).

 #. Put all necessary input files into this directory.

 #. Connect to the MySQL server using the `mysql` client on `modbase`, and the
    username and password from the web service's configuration file. Either the
    backend or frontend user can be used; the frontend user can only submit
    jobs and so is recommended, while the backend user can also delete or
    modify jobs, which is dangerous as it may break the service. For example,
    ``mysql -u modfoo_frontend -p -D modfoo``.

 #. To actually submit a job use something like::

     INSERT INTO jobs (name,passwd,user,contact_email,
                       directory,url,submit_time)
                      VALUES (a,b,c,d..., UTC_TIMESTAMP());

    a,b,c,d are the values for the columns, described below:

   * 'name' is the name of the job, from above.
   * 'passwd' is used by the frontend to protect job results. Any alphanumeric
     string can be used here.
   * 'user' is the user that submitted the job. NULL can be used here.
   * 'contact_email' is the email address that the backend will notify when
     the job completes, or NULL for no email notification.
   * 'directory' is the filesystem directory containing the job inputs, which
     must match that created above.
   * 'url' is a web link that the backend will include in the email it sends
     out, telling the user where the results can be downloaded. A dummy value
     can be used here, since the frontend usually handles this.
   * 'submit_time' is the time (UTC) when the job was submitted. Usually, the
     MySQL function UTC_TIMESTAMP() is used here to put in the current time.

 5. The job will only be run if the backend is running (use the `bin/service.py`
    script as the backend user in the installation directory). The backend
    polls periodically for new jobs. Alternatively, `service.py` can be used
    to restart the backend, to force it to check immediately.
