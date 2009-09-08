import subprocess
import re
import sys
import os.path
import datetime
import shutil
import time
import ConfigParser
import traceback
from email.MIMEText import MIMEText

# Version check; we need 2.4 for subprocess, decorators, generator expressions
if sys.version_info[0:2] < [2,4]:
    raise ImportError("This module requires Python 2.4 or later")

class InvalidStateError(Exception):
    """Exception raised for invalid job states."""
    pass

class RunnerError(Exception):
    """Exception raised if the runner (such as SGE) failed to run a job."""
    pass

class StateFileError(Exception):
    "Exception raised if a previous run is still running or crashed."""
    pass

class ConfigError(Exception):
    """Exception raised if a configuration file is inconsistent."""
    pass

class SanityError(Exception):
    """Exception raised if a new job fails the sanity check, e.g. if the
       frontend added invalid or inconsistent information to the database."""
    pass

class _JobState(object):
    """Simple state machine for jobs."""
    __valid_states = ['INCOMING', 'PREPROCESSING', 'RUNNING',
                      'POSTPROCESSING', 'COMPLETED', 'FAILED',
                      'EXPIRED', 'ARCHIVED']
    __valid_transitions = [['INCOMING', 'PREPROCESSING'],
                           ['PREPROCESSING', 'RUNNING'],
                           ['PREPROCESSING', 'COMPLETED'],
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
        return "<_JobState %s>" % self.get()

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
       locations, etc. `fh` is either a filename or a file handle from which
       the configuration is read."""
    _mailer = '/usr/sbin/sendmail'

    def __init__(self, fh):
        config = ConfigParser.SafeConfigParser()
        if not hasattr(fh, 'read'):
            self._config_dir = os.path.dirname(os.path.abspath(fh))
            config.readfp(open(fh), fh)
            fh = open(fh)
        else:
            self._config_dir = None
            config.readfp(fh)
        self._populate_database(config)
        self._populate_directories(config)
        self._populate_oldjobs(config)
        self.admin_email = config.get('general', 'admin_email')
        self.service_name = config.get('general', 'service_name')
        self.state_file = config.get('general', 'state_file')

    def send_admin_email(self, subject, body):
        """Send an email to the admin for this web service, with the given
           `subject` and `body`."""
        self.send_email(to=self.admin_email, subject=subject, body=body)

    def send_email(self, to, subject, body):
        """Send an email to the given user or list of users (`to`), with
           the given `subject` and `body`."""
        if not isinstance(to, (list, tuple)):
            to = [to]
        elif not isinstance(to, list):
            to = list(to)
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = self.admin_email
        msg['To'] = ", ".join(to)

        # Send email via sendmail binary
        p = subprocess.Popen([self._mailer, '-oi'] + to,
                             stdin=subprocess.PIPE)
        p.stdin.write(msg.as_string())
        p.stdin.close()
        p.wait()  # ignore return code for now

    def _populate_database(self, config):
        self.database = {}
        self.database['db'] = config.get('database', 'db')
        for key in ('backend_config', 'frontend_config'):
            fname = config.get('database', key)
            if not os.path.isabs(fname) and self._config_dir:
                fname = os.path.abspath(os.path.join(self._config_dir, fname))
            self.database[key] = fname

    def _read_db_auth(self, end='back'):
        filename = self.database[end + 'end_config']
        config = ConfigParser.SafeConfigParser()
        config.readfp(open(filename), filename)
        for key in ('user', 'passwd'):
            self.database[key] = config.get(end + 'end_db', key)

    def _populate_directories(self, config):
        self.directories = {}
        self.directories['install'] = config.get('directories', 'install')
        others = _JobState.get_valid_states()
        others.remove('EXPIRED')
        # INCOMING and PREPROCESSING directories must be specified
        for key in ('INCOMING', 'PREPROCESSING'):
            others.remove(key)
            self.directories[key] = config.get('directories', key)
        # Other directories (except EXPIRED) are optional:
        # default to PREPROCESSING
        for key in others:
            if config.has_option('directories', key):
                self.directories[key] = config.get('directories', key)
            else:
                self.directories[key] = self.directories['PREPROCESSING']

    def _populate_oldjobs(self, config):
        self.oldjobs = {}
        for key in ('archive', 'expire'):
            self.oldjobs[key] = self._get_time_delta(config, 'oldjobs', key)
        archive = self.oldjobs['archive']
        expire = self.oldjobs['expire']
        # archive time must not be greater than expire (None counts as infinity)
        if expire is not None and (archive is None or archive > expire):
            raise ConfigError("archive time (%s) cannot be greater than "
                              "expire time (%s)" \
                              % (config.get('oldjobs', 'archive'),
                                 config.get('oldjobs', 'expire')))

    def _get_time_delta(self, config, section, option):
        raw = config.get(section, option)
        try:
            if raw.endswith('h'):
                return datetime.timedelta(seconds=float(raw[:-1]) * 60 * 60)
            elif raw.endswith('d'):
                return datetime.timedelta(days=float(raw[:-1]))
            elif raw.endswith('m'):
                return datetime.timedelta(days=float(raw[:-1]) * 30)
            elif raw.endswith('y'):
                return datetime.timedelta(days=float(raw[:-1]) * 365)
            elif raw.upper() == 'NEVER':
                return None
        except ValueError:
            pass
        raise ValueError("Time deltas must be 'NEVER' or numbers followed "
                         "by h, d, m or y (for hours, days, months, or "
                         "years), e.g. 24h, 30d, 3m, 1y; got " + raw)


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
    _jobtable = 'jobs'

    def __init__(self, jobcls):
        self._jobcls = jobcls
        self._fields = []
        # Add fields used by all web services
        states = ", ".join("'%s'" % x for x in _JobState.get_valid_states())
        self.add_field(MySQLField('name', 'VARCHAR(40) PRIMARY KEY NOT NULL'))
        self.add_field(MySQLField('user', 'VARCHAR(40)'))
        self.add_field(MySQLField('passwd', 'CHAR(10)'))
        self.add_field(MySQLField('contact_email', 'VARCHAR(100)'))
        self.add_field(MySQLField('directory', 'TEXT'))
        self.add_field(MySQLField('url', 'TEXT NOT NULL'))
        self.add_field(MySQLField('state',
                              "ENUM(%s) NOT NULL DEFAULT 'INCOMING'" % states))
        self.add_field(MySQLField('submit_time', 'DATETIME NOT NULL'))
        self.add_field(MySQLField('preprocess_time', 'DATETIME'))
        self.add_field(MySQLField('run_time', 'DATETIME'))
        self.add_field(MySQLField('postprocess_time', 'DATETIME'))
        self.add_field(MySQLField('end_time', 'DATETIME'))
        self.add_field(MySQLField('archive_time', 'DATETIME'))
        self.add_field(MySQLField('expire_time', 'DATETIME'))
        self.add_field(MySQLField('runner_id', 'VARCHAR(50)'))
        self.add_field(MySQLField('failure', 'TEXT'))

    def add_field(self, field):
        """Add a new field (typically a :class:`MySQLField` object) to each
           table in the database. Usually called in the constructor or
           immediately after creating the :class:`Database` object."""
        self._fields.append(field)

    def _connect(self, config):
        """Set up the connection to the database. Usually called from the
           :class:`WebService` object."""
        import MySQLdb
        self._placeholder = '%s'
        self.config = config
        self.conn = MySQLdb.connect(user=config.database['user'],
                                    db=config.database['db'],
                                    passwd=config.database['passwd'])

    def _delete_tables(self):
        """Delete all tables in the database used to hold job state."""
        c = self.conn.cursor()
        c.execute('DROP TABLE IF EXISTS ' + self._jobtable)
        self.conn.commit()

    def _create_tables(self):
        """Create all tables in the database to hold job state."""
        c = self.conn.cursor()
        schema = ', '.join(x.get_schema() for x in self._fields)
        c.execute('CREATE TABLE %s (%s)' % (self._jobtable, schema))
        self.conn.commit()

    def _get_all_jobs_in_state(self, state, name=None, after_time=None):
        """Get all the jobs in the given job state, as a generator of
           :class:`Job` objects (or a subclass, as given by the `jobcls`
           argument to the :class:`Database` constructor).
           If `name` is specified, only jobs which match the given name are
           returned.
           If `after_time` is specified, only jobs where the time (given in
           the database column of the same name) is less than the current
           system time are returned.
        """
        fields = [x.name for x in self._fields]
        query = 'SELECT ' + ', '.join(fields) + ' FROM ' + self._jobtable
        wheres = ['state=' + self._placeholder]
        params = [state]
        if name is not None:
            wheres.append('name=' + self._placeholder)
            params.append(name)
        if after_time is not None:
            wheres.append(after_time + ' IS NOT NULL')
            wheres.append(after_time + ' < UTC_TIMESTAMP()')
        if wheres:
            query += ' WHERE ' + ' AND '.join(wheres)

        # Use regular cursor rather than MySQLdb.cursors.DictCursor, so we stay
        # reasonably database-independent
        c = self.conn.cursor()
        c.execute(query, params)
        for row in c:
            jobdict = dict(zip(fields, row))
            del jobdict['state']
            yield self._jobcls(self, jobdict, _JobState(state))

    def _update_job(self, jobdict, state):
        """Update a job in the job state table."""
        c = self.conn.cursor()
        query = 'UPDATE ' + self._jobtable + ' SET ' \
                + ', '.join(x + '=' + self._placeholder \
                            for x in jobdict.keys()) \
                + ' WHERE name=' + self._placeholder
        c.execute(query, jobdict.values() + [jobdict['name']])
        self.conn.commit()

    def _change_job_state(self, jobdict, oldstate, newstate):
        """Change the job state in the database. This has the side effect of
           updating the job (as if :meth:`_update_job` were called)."""
        c = self.conn.cursor()
        query = 'UPDATE ' + self._jobtable + ' SET ' \
                + ', '.join(x + '=' + self._placeholder \
                            for x in jobdict.keys() + ['state']) \
                + ' WHERE name=' + self._placeholder
        c.execute(query, jobdict.values() + [newstate, jobdict['name']])
        self.conn.commit()


class WebService(object):
    """Top-level class used by all web services. Pass in a :class:`Config`
       (or subclass) object for the `config` argument, and a :class:`Database`
       (or subclass) object for the `db` argument.
    """
    def __init__(self, config, db):
        self.config = config
        self.config._read_db_auth('back')
        self.__delete_state_file_on_exit = False
        self.db = db
        self.db._connect(config)

    def __del__(self):
        if self.__delete_state_file_on_exit:
            os.unlink(self.config.state_file)

    def _check_state_file(self, state_file):
        """Make sure that a previous run is not still running or encountered
           an unrecoverable error."""
        if self.__delete_state_file_on_exit: # state file checked already
            return
        try:
            old_state = open(state_file).read().rstrip('\r\n')
            if old_state.startswith('FAILED: '):
                raise StateFileError("A previous run failed with an "
                        "unrecoverable error. Since this can leave the system "
                        "in an inconsistent state, no further runs will start "
                        "until the problem has been manually resolved. When "
                        "you have done this, delete the state file "
                        "(%s) to reenable runs." % state_file)
            old_pid = int(old_state)
            try:
                os.kill(old_pid, 0)
                raise StateFileError("A previous run (pid %d) " % old_pid + \
                        "still appears to be running. If this is not the "
                        "case, please manually remove the state "
                        "file (%s)." % state_file)
            except OSError:
                pass
        except IOError:
            pass
        f = open(state_file, 'w')
        print >> f, os.getpid()
        self.__delete_state_file_on_exit = True

    def _handle_fatal_error(self, detail):
        err = traceback.format_exc()
        if err is None:
            err = 'Error: ' + str(detail)
        if hasattr(detail, 'original_error'):
            err += "\n\nThis error in turn occurred while trying to " + \
                   "handle the original error below:\n" + detail.original_error
        f = open(self.config.state_file, 'w')
        print >> f, "FAILED: " + err
        f.close()
        self.__delete_state_file_on_exit = False
        subject = 'Sali lab %s service: SHUTDOWN WITH FATAL ERROR' \
                  % self.config.service_name
        body = """
The %s service encounted an unrecoverable error and
has been shut down.

%s

Since this can leave the system in an inconsistent state, no further
runs will start until the problem has been manually resolved. When you
have done this, delete the state file (%s) to reenable runs.
""" % (self.config.service_name, err, self.config.state_file)
        self.config.send_admin_email(subject, body)
        raise

    def get_job_by_name(self, state, name):
        """Get the job with the given name in the given job state. Returns
           a :class:`Job` object, or None if the job is not found."""
        jobs = list(self.db._get_all_jobs_in_state(state, name=name))
        if len(jobs) == 1:
            return jobs[0]

    def delete_database_tables(self):
        """Delete all tables in the database used to hold job state."""
        self.db._delete_tables()

    def create_database_tables(self):
        """Create all tables in the database used to hold job state."""
        self.db._create_tables()

    def do_all_processing(self):
        """Process incoming jobs, completed jobs, and old jobs."""
        self._process_incoming_jobs()
        self._process_completed_jobs()
        self._process_old_jobs()

    def _process_incoming_jobs(self):
        """Check for any incoming jobs, and run each one."""
        self._check_state_file(self.config.state_file)
        try:
            for job in self.db._get_all_jobs_in_state('INCOMING'):
                job._try_run()
        except Exception, detail:
            self._handle_fatal_error(detail)

    def _process_completed_jobs(self):
        """Check for any jobs that have just completed, and process them."""
        self._check_state_file(self.config.state_file)
        try:
            for job in self.db._get_all_jobs_in_state('RUNNING'):
                job._try_complete()
        except Exception, detail:
            self._handle_fatal_error(detail)

    def _process_old_jobs(self):
        """Check for any old job results and archive or delete them."""
        self._check_state_file(self.config.state_file)
        try:
            for job in self.db._get_all_jobs_in_state('COMPLETED',
                                                     after_time='archive_time'):
                job._try_archive()
            for job in self.db._get_all_jobs_in_state('ARCHIVED',
                                                      after_time='expire_time'):
                job._try_expire()
        except Exception, detail:
            self._handle_fatal_error(detail)


class Job(object):
    """Class that encapsulates a single job in the system. Jobs are not
       created by the user directly, but by querying a :class:`WebService`
       object.
    """

    _state_file_wait_time = 5.0
    _runners = {}

    # Note: make sure that all code paths are wrapped with try/except, so that
    # if an exception occurs, it is caught and _fail() is called. Note that some
    # exceptions (e.g. qstat failure) should perhaps be ignored, as they may be
    # transient and do not directly affect the job.
    def __init__(self, db, jobdict, state):
        # todo: Sanity check; make sure jobdict is OK (if not, call _fail)
        self._db = db
        self._jobdict = jobdict
        self.__state = state

    @classmethod
    def _register_runner_class(cls, runnercls):
        """Maintain a mapping from names to :class:`Runner` classes. Should
           normally be called from :meth:`Runner.__init__`."""
        exist = cls._runners.get(runnercls._runner_name, None)
        if exist is not None and exist is not runnercls:
            # Runner name must be unique
            raise TypeError("Two Runner classes have the same name (%s): "
                            "%s and %s" % (runnercls._runner_name, exist,
                                           runnercls))
        cls._runners[runnercls._runner_name] = runnercls

    def _get_job_state_file(self):
        return os.path.join(self.directory, 'job-state')

    def _run_in_job_directory(self, meth, *args, **keys):
        """Run a method with the working directory set to the job directory.
           Restore the cwd after the method completes."""
        cwd = os.getcwd()
        try:
            os.chdir(self.directory)
            return meth(*args, **keys)
        finally:
            os.chdir(cwd)

    def _frontend_sanity_check(self):
        """Make sure that the frontend set up the job correctly."""
        # SQL schema should not allow this, but check anyway just to be sure:
        if self.name is None:
            raise SanityError("Frontend did not set the job name")
        if self.directory is None:
            raise SanityError("Frontend did not set the directory field in the "
                              "database for job %s" % self.name)
        if not os.path.isdir(self.directory):
            # Set directory to None otherwise _fail() will itself fail, since it
            # won't be able to move the (invalid) directory
            dir = self.directory
            self._jobdict['directory'] = None
            self._db._update_job(self._jobdict, self._get_state())
            raise SanityError("Job %s: directory %s is not a directory" \
                              % (self.name, dir))

    def _try_run(self):
        """Take an incoming job and try to start running it."""
        try:
            self._frontend_sanity_check()
            self._jobdict['preprocess_time'] = datetime.datetime.utcnow()
            self._set_state('PREPROCESSING')
            # Delete job-state file, if present from a previous run
            try:
                os.unlink(self._get_job_state_file())
            except OSError:
                pass
            if self._run_in_job_directory(self.preprocess) is False:
                self._mark_job_completed()
            else:
                self._jobdict['run_time'] = datetime.datetime.utcnow()
                self._set_state('RUNNING')
                runner = self._run_in_job_directory(self.run)
                runner_id = runner._runner_name + ':' + runner._run()
                if runner_id != self._jobdict['runner_id']:
                    self._jobdict['runner_id'] = runner_id
                    self._db._update_job(self._jobdict, self._get_state())
        except Exception, detail:
            self._fail(detail)

    def _job_state_file_done(self):
        """Return True only if the job-state file indicates the job finished."""
        try:
            f = open(self._get_job_state_file())
            return f.read().rstrip('\r\n') == 'DONE'
        except IOError:
            return False   # if the file does not exist, job is still running

    def _runner_done(self):
        """Return True if the job's :class:`Runner` indicates the job finished,
           or None if that cannot be determined."""
        runner_id = self._jobdict['runner_id']
        runner_name, jobid = runner_id.split(':')
        runnercls = self._runners[runner_name]
        return runnercls._check_completed(jobid)

    def _has_completed(self):
        """Return True only if the job has just finished running. This is not
           the case until the :class:`Runner` reports the job has finished
           (if it is able to) and the state file has been updated, since the
           state file is created when the first task in a multi-task SGE job
           finishes, so other SGE tasks may still be running."""
        batch_done = self._runner_done()
        state_file_done = self._job_state_file_done()
        if state_file_done and batch_done is not False:
            return True
        elif batch_done and not state_file_done:
            # This usually means the batch job failed; check state file again,
            # since the batch job may have just finished, after the first
            # check above; we may have to wait a little while for
            # NFS caching, etc.
            for tries in range(5):
                state_file_done = self._job_state_file_done()
                if state_file_done:
                    return True
                time.sleep(self._state_file_wait_time)
            raise RunnerError(
                 "Runner claims job %s is complete, but "
                 "job-state file in job directory (%s) claims it "
                 "is not. This usually means the underlying batch system "
                 "(e.g. SGE) job failed - e.g. a node went down." \
                 % (self._jobdict['runner_id'], self._jobdict['directory']))
        return False

    def _try_complete(self):
        """Take a running job, see if it completed, and if so, process it."""
        try:
            self._assert_state('RUNNING')
            if not self._has_completed():
                return
            # Delete job-state file; no longer needed
            os.unlink(self._get_job_state_file())
            self._jobdict['postprocess_time'] = datetime.datetime.utcnow()
            self._set_state('POSTPROCESSING')
            self._run_in_job_directory(self.postprocess)
            self._mark_job_completed()
        except Exception, detail:
            self._fail(detail)

    def _mark_job_completed(self):
        endtime = datetime.datetime.utcnow()
        self._jobdict['end_time'] = endtime
        archive_time = self._db.config.oldjobs['archive']
        if archive_time is not None:
            archive_time = endtime + archive_time
        expire_time = self._db.config.oldjobs['expire']
        if expire_time is not None:
            expire_time = endtime + expire_time
        self._jobdict['archive_time'] = archive_time
        self._jobdict['expire_time'] = expire_time
        self._set_state('COMPLETED')
        self._run_in_job_directory(self.complete)
        self.send_job_completed_email()

    def _try_archive(self):
        try:
            self._set_state('ARCHIVED')
            self._run_in_job_directory(self.archive)
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
        if state == 'EXPIRED':
            shutil.rmtree(self._jobdict['directory'])
            self._jobdict['directory'] = None
        elif self._jobdict['directory'] is not None:
            # move job to different directory if necessary
            directory = os.path.join(self._db.config.directories[state],
                                     self.name)
            directory = os.path.normpath(directory)
            if directory != self._jobdict['directory']:
                shutil.move(self._jobdict['directory'], directory)
                self._jobdict['directory'] = directory
        self._db._change_job_state(self._jobdict, oldstate, state)

    def _get_state(self):
        """Get the job state as a string."""
        return self.__state.get()

    def _fail(self, reason):
        """Mark a job as FAILED. Generally, it should not be necessary to call
           this method directly - instead, simply raise an exception.
           `reason` should be an exception object.
           If an exception in turn occurs in this method, it is considered an
           unrecoverable error (and is usually handled by :class:`WebService`.
        """
        err = traceback.format_exc()
        if err is None:
            err = str(reason)
        reason = "Python exception:\n" + err
        try:
            self._jobdict['failure'] = reason
            self.__internal_set_state('FAILED')
            subject = 'Sali lab %s service: Job %s FAILED' \
                      % (self.service_name, self.name)
            body = 'Job %s failed with the following error:\n' \
                   % self.name + reason
            self._db.config.send_admin_email(subject, body)
        except Exception, detail:
            # Ensure we can extract the original error
            detail.original_error = reason
            raise

    def _assert_state(self, state):
        """Make sure that the current job state (as a string) matches
           `state`. If not, an :exc:`InvalidStateError` is raised."""
        current_state = self.__state.get()
        if state != current_state:
            raise InvalidStateError(("Expected job to be in %s state, " + \
                                     "but it is actually in %s state") \
                                    % (state, current_state))

    def resubmit(self):
        """Make a FAILED job eligible for running again."""
        self._assert_state('FAILED')
        self._set_state('INCOMING')

    def run(self):
        """Run the job, e.g. on an SGE cluster.
           Must be implemented by the user for each web service; it should
           create and return a suitable :class:`Runner` instance.
           For example, this could generate a simple script and pass it to
           an :class:`SGERunner` instance.
        """

    def send_user_email(self, subject, body):
        """Email the owner of the job, if requested, with the given `subject`
           and `body`."""
        if self._jobdict['contact_email']:
            self._db.config.send_email(self._jobdict['contact_email'],
                                       subject, body)

    def complete(self):
        """This method is called after a job completes. Does nothing by default,
           but can be overridden by the user.
        """

    def send_job_completed_email(self):
        """Email the user (if requested) to let them know job results are
           available. Can be overridden to disable this behavior or to change
           the content of the email."""
        subject = 'Sali lab %s service: Job %s complete' \
                  % (self.service_name, self.name)
        body = 'Your job %s has finished.\n\n' % self.name + \
               'Results can be found at %s\n' % self.url
        self.send_user_email(subject, body)

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
           Does nothing by default. If this method returns False, further
           running of the job is skipped and it moves directly to the
           COMPLETED state."""

    def postprocess(self):
        """Do any necessary postprocessing when the job completes successfully.
           Does nothing by default."""

    name = property(lambda x: x._jobdict['name'],
                    doc="Unique job name (read-only)")
    url = property(lambda x: x._jobdict['url'],
                   doc="URL containing job results (read-only)")
    service_name = property(lambda x: x._db.config.service_name,
                            doc="Web service name (read-only)")
    directory = property(lambda x: x._jobdict['directory'],
                         doc="Current job working directory (read-only)")

class Runner(object):
    """Base class for runners, which handle the actual running of a job,
       usually on an SGE cluster (see the :class:`SGERunner` and
       :class:`SaliSGERunner` subclasses). To create a subclass, you must
       implement both a _run method and a _check_completed class method and
       set the _runner_name attribute to a unique name for this class."""
    def __init__(self):
        Job._register_runner_class(self.__class__)

class SGERunner(Runner):
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
       options.
    """

    _runner_name = 'qb3sge'
    _env = {'SGE_CELL': 'qb3',
            'SGE_ROOT': '/ccpr1/sge6',
            'SGE_QMASTER_PORT': '536',
            'SGE_EXECD_PORT': '537'}
    _arch = 'lx24-amd64'

    def __init__(self, script, interpreter='/bin/sh'):
        Runner.__init__(self)
        self._opts = ''
        self._script = script
        self._interpreter = interpreter

    def set_sge_options(self, opts):
        """Set the SGE options to use, as a string,
           for example '-N foo -l mydisk=1G'
        """
        self._opts = opts

    def _run(self):
        """Generate an SGE script in the current directory and run it.
           Return the SGE job ID."""
        fh = open('sge-script.sh', 'w')
        self._write_sge_script(fh)
        fh.close()
        return self._qsub('sge-script.sh')

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
    def _qsub(cls, script):
        """Submit a job script to the cluster."""
        cmd = '%s/bin/%s/qsub' % (cls._env['SGE_ROOT'], cls._arch)
        p = subprocess.Popen([cmd, script], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, env=cls._env)
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
    def _check_completed(cls, jobid, catch_exceptions=True):
        """Return True if SGE reports that the given job has finished, False
           if it is still running, or None if the status cannot be determined.
           If `catch_exceptions` is True and a problem occurs when talking to
           SGE, None is returned; otherwise, the exception is propagated."""
        try:
            cmd = '%s/bin/%s/qstat' % (cls._env['SGE_ROOT'], cls._arch)
            p = subprocess.Popen([cmd, '-j', jobid], stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, env=cls._env)
            out = p.stdout.read()
            err = p.stderr.read()
            ret = p.wait()
            if ret > 1:
                raise OSError("qstat failed with code %d and stderr %s" \
                              % (ret, err))
        except Exception:
            if catch_exceptions:
                return None
            else:
                raise
        # todo: raise an exception if job is in Eqw state, dr, etc.
        return err.startswith("Following jobs do not exist:")


class SaliSGERunner(SGERunner):
    """Run commands on the Sali SGE cluster instead of the QB3 cluster."""
    _runner_name = 'salisge'
    _env = {'SGE_CELL': 'sali',
            'SGE_ROOT': '/home/sge61'}
