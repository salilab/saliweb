import subprocess
import re
import sys
import datetime

# Version check; we need 2.4 for subprocess, decorators, generator expressions
if sys.version_info[0:2] < [2,4]:
    raise ImportError("This module requires Python 2.4 or later")

class InvalidStateError(Exception):
    """Exception raised for invalid job states."""
    pass

class BatchSystemError(Exception):
    "Exception raised if the batch system (such as SGE) failed to run a job."
    pass

class JobState(object):
    """Simple state machine for jobs."""
    __valid_states = ['INCOMING', 'PREPROCESSING', 'RUNNING',
                      'POSTPROCESSING', 'COMPLETED', 'FAILED',
                      'EXPIRED', 'ARCHIVED']
    __valid_transitions = [['INCOMING', 'PREPROCESSING'],
                           ['PREPROCESSING', 'RUNNING'],
                           ['RUNNING', 'POSTPROCESSING'],
                           ['POSTPROCESSING', 'COMPLETED'],
                           ['COMPLETED', 'ARCHIVED'],
                           ['ARCHIVED', 'EXPIRED'],
                           ['FAILED', 'INCOMING']]
    def __init__(self, state):
        if state in self.__valid_states:
            self.__state = state
        else:
            raise InvalidStateError("%s is not in %s" \
                                    % (state, str(self.__valid_states)))
    def __str__(self):
        return "<JobState %s>" % self.get()

    def get(self):
        """Get current state, as a string."""
        return self.__state

    @classmethod
    def get_valid_states(cls):
        """Get all valid job states, as a list of strings."""
        return cls.__valid_states[:]

    def transition(self, newstate):
        """Change state to `newstate`. Raises an :exc:`InvalidStateError` if
           the new state is not valid."""
        tran = [self.__state, newstate]
        if newstate == 'FAILED' or tran in self.__valid_transitions:
            self.__state = newstate
        else:
            raise InvalidStateError("Cannot transition from %s to %s" \
                                    % (self.__state, newstate))


class Config(object):
    """This class holds configuration information such as directory
       locations, etc."""
    # config.archive_time and config.expire_time are datetime.timedelta objects
    # e.g. datetime.timedelta(days=30)

    def __init__(self, fname):
        """Read configuration data from a file."""
        # todo: implement this method
        pass


class MySQLField(object):
    """Description of a single field in a MySQL database. Each field must have
       a unique `name` (e.g. 'user') and a given `sqltype`
       (e.g. 'VARCHAR(15) PRIMARY KEY NOT NULL')."""
    def __init__(self, name, sqltype):
        self.name = name
        self.sqltype = sqltype

    def get_schema(self):
        """Get the SQL schema needed to create a table containing this field."""
        return self.name + " " + self.sqltype


class Database(object):
    """Management of the job database.
       Can be subclassed to add extra columns to the tables for
       service-specific metadata, or to use a different database engine.
       `jobcls` should be a subclass of :class:`Job`, which will be used to
       instantiate new job objects.
    """
    def __init__(self, jobcls):
        self._jobcls = jobcls
        self._fields = []
        # Add fields used by all web services
        self.add_field(MySQLField('name', 'VARCHAR(15) PRIMARY KEY NOT NULL'))
        self.add_field(MySQLField('user', 'VARCHAR(40)'))
        self.add_field(MySQLField('contact_email', 'VARCHAR(100)'))
        self.add_field(MySQLField('directory', 'VARCHAR(400)'))
        self.add_field(MySQLField('submit_time', 'DATETIME NOT NULL'))
        self.add_field(MySQLField('preprocess_time', 'DATETIME'))
        self.add_field(MySQLField('run_time', 'DATETIME'))
        self.add_field(MySQLField('postprocess_time', 'DATETIME'))
        self.add_field(MySQLField('end_time', 'DATETIME'))
        self.add_field(MySQLField('archive_time', 'DATETIME'))
        self.add_field(MySQLField('expire_time', 'DATETIME'))
        self.add_field(MySQLField('runjob_id', 'VARCHAR(50)'))
        self.add_field(MySQLField('failure', 'VARCHAR(400)'))

    def add_field(self, field):
        """Add a new field (typically a :class:`MySQLField` object) to each
           table in the database. Usually called in the constructor or
           immediately after creating the :class:`Database` object."""
        self._fields.append(field)

    def _connect(self, config):
        """Set up the connection to the database. Usually called from the
           :class:`WebService` object."""
        self.conn = MySQLdb.connect(user=config['dbuser'],
                                    db=config['db'],
                                    passwd=config['dbpasswd'])

    def delete_tables(self):
        """Delete all tables in the database used to hold job state."""
        c = self.conn.cursor()
        for state in JobState.get_valid_states():
            c.execute('drop table if exists %s' % state)
        c.commit()

    def create_tables(self):
        """Create all tables in the database to hold job state."""
        c = self.conn.cursor()
        schema = ', '.join(x.get_schema() for x in self._fields)
        for state in JobState.get_valid_states():
            c.execute('create table %s (%s)' % (state, schema))
        c.commit()

    def get_all_jobs_in_state(self, state, name=None, after_time=None):
        """Get all the jobs in the given job state, as a generator of
           :class:`Job` objects (or a subclass, as given by the `jobcls`
           argument to the :class:`Database` constructor).
           If `name` is specified, only jobs which match the given name are
           returned.
           If `after_time` is specified, only jobs where the time (given in
           the database column of the same name) is greater than the current
           system time are returned.
        """
        query = 'SELECT * FROM ' + state
        wheres = []
        params = []
        if name is not None:
            wheres.append('name=%%s')
            params.append(name)
        if after_time is not None:
            wheres.append('%%s < UTC_TIMESTAMP()')
            params.append(after_time)
        if wheres:
            query += ' WHERE ' + ', '.join(wheres)

        c = self.conn.cursor(MySQLdb.cursors.DictCursor)
        c.execute(query, params)
        for row in c:
            yield self._jobcls(self, row, JobState(state))

    def _update_job(self, jobdict, state):
        """Update a job in the job state table."""
        c = self.conn.cursor()
        query = 'UPDATE ' + state + ' SET ' \
                + ', '.join("%s=%%s" % x for x in jobdict.keys()) \
                + ' WHERE name=%s'
        c.execute(query, jobdict.values() + [jobdict['name']])
        c.commit()

    def _change_job_state(self, jobdict, oldstate, newstate):
        """Change the job state in the database. This has the side effect of
           updating the job (effectively calling :meth:`_update_job`)."""
        # Remove from the old state table, and add to the new state table
        c = self.conn.cursor()
        c.execute('REMOVE FROM ' + oldstate + ' WHERE name=%s',
                  (jobdict['name'],))
        query = 'INSERT INTO ' + state + ' SET ' \
                + ', '.join("%s=%%s" % x for x in jobdict.keys())
        c.execute(query, jobdict.values())
        c.commit()


class WebService(object):
    """Top-level class used by all web services. Pass in a :class:`Config`
       (or subclass) object for the `config` argument, and a :class:`Database`
       (or subclass) object for the `db` argument.
    """
    def __init__(self, config, db):
        self.config = config
        self.db = db
        self.db._connect(config)

    def get_job_by_name(self, state, name):
        """Get the job with the given name in the given job state. Returns
           a :class:`Job` object, or None if the job is not found."""
        jobs = list(self.db.get_all_jobs_in_state(state, name=name))
        if len(jobs) == 1:
            return jobs[0]

    def do_all_processing(self):
        """Convenience method that calls each of the process_* methods"""
        self.process_incoming_jobs()
        self.process_completed_jobs()
        self.process_old_jobs()

    def process_incoming_jobs(self):
        """Check for any incoming jobs, and run each one."""
        for job in self.db.get_all_jobs_in_state('INCOMING'):
            job._try_run()

    def process_completed_jobs(self):
        """Check for any jobs that have just completed, and process them."""
        for job in self.db.get_all_jobs_in_state('RUNNING'):
            job._try_complete()

    def process_old_jobs(self):
        """Check for any old job results and archive or delete them."""
        # todo: Use a state file to ensure this is run only once per day?
        for job in self.db.get_all_jobs_in_state('COMPLETED',
                                                 after_time='archive_time'):
            job._try_archive()
        for job in self.db.get_all_jobs_in_state('ARCHIVED',
                                                 after_time='expire_time'):
            job._try_expire()


class Job(object):
    """Class that encapsulates a single job in the system. Jobs are not
       created by the user directly, but by querying a :class:`WebService`
       object.
    """

    # Note: make sure that all code paths are wrapped with try/except, so that
    # if an exception occurs, it is caught and _fail() is called. Note that some
    # exceptions (e.g. qstat failure) should perhaps be ignored, as they may be
    # transient and do not directly affect the job.
    def __init__(self, db, jobdict, state):
        # todo: Sanity check; make sure jobdict is OK (if not, call _fail)
        self._db = db
        self._jobdict = jobdict
        self.__state = state

    def _try_run(self):
        """Take an incoming job and try to start running it."""
        try:
            self._jobdict['preprocess_time'] = datetime.datetime.utcnow()
            self._set_state('PREPROCESSING')
            self.preprocess()
            self._jobdict['run_time'] = datetime.datetime.utcnow()
            self._set_state('RUNNING')
            jobid = self.run()
            if jobid != self._jobdict['runjob_id']:
                self._jobdict['runjob_id'] = jobid
                self._db._update_job(self._jobdict, self._get_state())
        except Exception, detail:
            self._fail(detail)

    def _job_state_file_done(self):
        """Return True only if the job-state file indicates the job finished."""
        try:
            f = open(os.path.join(self._jobdict['directory'], 'job-state'))
            return f.read().rstrip('\r\n') == 'DONE'
        except IOError:
            return False   # if the file does not exist, job is still running

    def _has_completed(self):
        """Return True only if the job has just finished running."""
        state_file_done = self._job_state_file_done()
        if state_file_done:
            return True
        else:
            batch_done = self.check_batch_completed(self._jobdict['runjob_id'])
            if batch_done:
                raise BatchSystemError(
                     ("Batch system claims job %s is complete, but " + \
                      "job-state file in job directory (%s) claims it " + \
                      "is not. This usually means the batch system job " + \
                      "failed - e.g. a node went down.") \
                     % (self._jobdict['runjob_id'], self._jobdict['directory']))
            return False

    def _try_complete(self):
        """Take a running job, see if it completed, and if so, process it."""
        try:
            self._assert_state('RUNNING')
            if not self._has_completed():
                return
            self._jobdict['postprocess_time'] = datetime.datetime.utcnow()
            self._set_state('POSTPROCESSING')
            self.postprocess()
            endtime = datetime.datetime.utcnow()
            self._jobdict['end_time'] = endtime
            self._jobdict['archive_time'] = endtime \
                                            + self._config['archive_time']
            self._jobdict['expire_time'] = endtime \
                                           + self._config['expire_time']
            self._set_state('COMPLETED')
            # todo: email user if requested
        except Exception, detail:
            self._fail(detail)

    def _try_archive(self):
        try:
            self._set_state('ARCHIVED')
            self.archive()
        except Exception, detail:
            self._fail(detail)

    def _try_expire(self):
        try:
            self._set_state('EXPIRED')
            self.expire()
        except Exception, detail:
            self._fail(detail)

    def _set_state(self, state):
        """Change the job state to `state`."""
        try:
            self.__internal_set_state(state)
        except Exception, detail:
            self._fail(detail)

    def __internal_set_state(self, state):
        """Set job state. Does not catch any exceptions. Should only be called
           from :meth:`_fail`, which handles the exceptions itself. For all
           other uses, call :meth:`_set_state` instead."""
        oldstate = self._get_state()
        self.__state.transition(state)
        # todo: move job to different directory if necessary
        self.db._change_job_state(self._jobdict, oldstate, state)

    def _get_state(self):
        """Get the job state as a string."""
        return self.__state.get()

    def _fail(self, reason):
        """Mark a job as FAILED. Generally, it should not be necessary to call
           this method directly - instead, simply raise an exception.
           `reason` can be either a simple string or an exception object."""
        try:
            if isinstance(reason, Exception):
                reason = "Python exception " + str(reason)
            self._jobdict['failure'] = reason
            self.__internal_set_state('FAILED')
        except Exception, detail:
            # todo: if an exception occurs here, a catastrophic error occurred.
            # Email the admin?
            raise

    def _assert_state(self, state):
        """Make sure that the current job state (as a string) matches
           `state`. If not, an :exc:`InvalidStateError` is raised."""
        current_state = self.__state.get()
        if state != current_state:
            raise InvalidStateError(("Expected job to be in %s state, " + \
                                     "but it is actually in %s state") \
                                    % (state, current_state))

    def run(self):
        """Run the job, e.g. on an SGE cluster.
           Must be implemented by the user for each web service.
           For example, this could generate a simple script and pass it to
           an :class:`SGERunner` instance.
           If the job is run by something like :meth:`SGERunner.run`, the
           return value from that method should be returned here (it can be
           later used by :meth:`check_batch_completed`).
        """

    def check_batch_completed(self, runjob_id):
        """Query the batch system to see if the job has completed. Does
           nothing by default, but can be overridden by the user, for example
           to return the result of :meth:`SGERunner.check_completed`. The
           method should return True, False or None (the last if it is not
           possible to query the batch system).
           Note that the batch system reporting the job is complete does not
           necessarily mean the job actually completed successfully."""

    def archive(self):
        """Do any necessary processing when an old completed job reaches its
           archive time. Does nothing by default, but can be overridden by
           the user to compress files, etc."""

    def expire(self):
        """Do any necessary processing when an old completed job reaches its
           archive time. Does nothing by default, but can be overridden by
           the user to mail the admin, etc."""

    def preprocess(self):
        """Do any necessary preprocessing before the job is actually run.
           Does nothing by default."""

    def postprocess(self):
        """Do any necessary postprocessing when the job completes successfully.
           Does nothing by default."""


class SGERunner(object):
    """Run a set of commands on the QB3 SGE cluster.

       To use, pass a string `script` containing a set of commands to run,
       and use `interpreter` to specify the shell (e.g. `/bin/sh`, `/bin/csh`)
       or other interpreter (e.g. `/usr/bin/python`) that will run them.
       These commands will be automatically modified to update a job state
       file at job start and end, if your interpreter is `/bin/sh`, `/bin/csh`,
       `/bin/bash` or `/bin/tcsh`. If you want to use a different interpreter
       you will need to manually add code to your script to update a file
       called job-state in the working directory, to contain just the simple
       text "STARTED" (without the quotes) when the job starts and just
       "DONE" when it completes.

       Once done, you can optionally call :meth:`set_sge_options` to set SGE
       options, then call :meth:`run` to submit the job.
    """

    _env = {'SGE_CELL': 'qb3',
            'SGE_ROOT': '/ccpr1/sge6',
            'SGE_QMASTER_PORT': '536',
            'SGE_EXECD_PORT': '537'}
    _arch = 'lx24-amd64'

    def __init__(self, script, interpreter='/bin/sh'):
        self._opts = ''
        self._script = script
        self._interpreter = interpreter

    def set_sge_options(self, opts):
        """Set the SGE options to use, as a string,
           for example '-N foo -l mydisk=1G'
        """
        self._opts = opts

    def run(self, rundir):
        """Generate an SGE script in `rundir` and run it. Return the
           SGE job ID."""
        fh = open(os.path.join(rundir, 'sge-script.sh'), 'w')
        self._write_sge_script(fh)
        fh.close()
        return self._qsub(rundir, 'sge-script.sh')

    def _write_sge_script(self, fh):
        print >> fh, "#!" + self._interpreter
        print >> fh, "#$ -S " + self._interpreter
        print >> fh, "#$ -cwd"
        if self._opts:
            print >> fh, '#$ ' + self._opts
        # Update job state file at job start and end
        if self._interpreter in ('/bin/sh', '/bin/bash'):
            print >> fh, "_SALI_JOB_DIR=`pwd`"
        if self._interpreter in ('/bin/csh', '/bin/tcsh'):
            print >> fh, "setenv _SALI_JOB_DIR `pwd`"
        if self._interpreter in ('/bin/sh', '/bin/bash', '/bin/csh',
                                 '/bin/tcsh'):
            print >> fh, 'echo "STARTED" > ${_SALI_JOB_DIR}/job-state'
        print >> fh, self._script
        if self._interpreter in ('/bin/sh', '/bin/bash', '/bin/csh',
                                 '/bin/tcsh'):
            print >> fh, 'echo "DONE" > ${_SALI_JOB_DIR}/job-state'

    @classmethod
    def _qsub(cls, rundir, script):
        """Submit a job script to the cluster."""
        cmd = '%s/bin/%s/qsub' % (cls._env['SGE_ROOT'], cls._arch)
        p = subprocess.Popen([cmd, script], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, cwd=rundir, env=cls._env)
        out = p.stdout.read()
        err = p.stderr.read()
        ret = p.wait()
        if ret != 0:
            raise OSError("qsub failed with code %d and stderr %s" % (ret, err))
        m = re.match("Your job(\-array)? ([\d]+)(\.\d+\-\d+:\d+)? " + \
                     "\(.*\) has been submitted", out)
        if m:
            return m.group(2)
        else:
            raise OSError("Could not parse qsub output %s" % out)

    @classmethod
    def check_completed(cls, runjob_id, catch_exceptions=True):
        """Return True if SGE reports that the given job has finished, False
           if it is still running, or None if the status cannot be determined.
           If `catch_exceptions` is True and a problem occurs when talking to
           SGE, None is returned; otherwise, the exception is propagated."""
        try:
            cmd = '%s/bin/%s/qstat' % (cls._env['SGE_ROOT'], cls._arch)
            p = subprocess.Popen([cmd, '-j', runjob_id], stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, env=cls._env)
            out = p.stdout.read()
            err = p.stderr.read()
            ret = p.wait()
            if ret != 0:
                raise OSError("qstat failed with code %d and stderr %s" \
                              % (ret, err))
        except Exception:
            if catch_exceptions:
                return None
            else:
                raise
        # todo: raise an exception if job is in Eqw state, dr, etc.
        return out.startswith("Following jobs do not exist:")


class SaliSGERunner(SGERunner):
    """Run commands on the Sali SGE cluster instead of the QB3 cluster."""
    _env = {'SGE_CELL': 'sali',
            'SGE_ROOT': '/home/sge61'}
