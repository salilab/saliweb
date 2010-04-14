import subprocess
import re
import glob
import sys
import os.path
import datetime
import shutil
import time
import ConfigParser
import traceback
import select
import signal
import socket
import logging
import threading
import saliweb.backend.events
import saliweb.backend.sge
from saliweb.backend.events import _JobThread
from email.MIMEText import MIMEText

# Version check; we need 2.4 for subprocess, decorators, generator expressions
if sys.version_info[0:2] < [2, 4]:
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


class _SigTermError(Exception):
    """Exception raised if the daemon is killed by SIGTERM."""
    pass


def _sigterm_handler(signum, frame):
    """Catch SIGTERM and convert it to a SigTermError exception."""
    raise _SigTermError()


def _make_daemon():
    """Make the current process into a daemon, by forking twice and detaching
       from the controlling terminal. On the parent, this function does not
       return."""
    pid = os.fork()
    if pid != 0:
        os._exit(0)
    # First child; detach from the controlling terminal
    os.setsid()
    pid = os.fork()
    if pid != 0:
        os._exit(0)
    # Second child; make sure we don't live on a mounted filesystem,
    # and redirect standard file descriptors to /dev/null:
    os.chdir('/')
    for fd in range(0, 3):
        try:
            os.close(fd)
        except OSError:
            pass
    # This call to open is guaranteed to return the lowest file descriptor,
    # which will be 0 (stdin), since it was closed above.
    os.open('/dev/null', os.O_RDWR)
    os.dup2(0, 1)
    os.dup2(0, 2)


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
                           ['POSTPROCESSING', 'RUNNING'],
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


class _JobMetadata(object):
    """A dictionary-like class that holds job metadata (a database row).
       Objects also keep track of whether metadata needs to be pushed back to
       the database to keep things synchronized.
       Keys cannot be removed or added."""

    def __init__(self, keys, values):
        self.__dict = dict(zip(keys, values))
        del self.__dict['state']
        self.mark_synced()

    def needs_sync(self):
        return self.__needs_sync

    def mark_synced(self):
        self.__needs_sync = False

    def __getitem__(self, key):
        return self.__dict[key]

    def __setitem__(self, key, value):
        old = self.__dict[key]
        if old != value:
            self.__needs_sync = True
            self.__dict[key] = value

    def keys(self):
        return self.__dict.keys()

    def values(self):
        return self.__dict.values()

    def get(self, k, d=None):
        return self.__dict.get(k, d)


class _DelayFileStream(object):
    """A simple file-like object that writes to a file, but does not open the
       file until the first write occurs. This is intended to be used with
       the logging support (see :meth:`Job.get_log_handler`) and is provided
       for older Pythons that do not have the 'delay' argument to
       logging.FileHandler."""

    def __init__(self, filename):
        self.filename = os.path.abspath(filename)
        self.stream = None

    def write(self, txt):
        if self.stream is None:
            self.stream = open(self.filename, 'a')
        self.stream.write(txt)

    def flush(self):
        if self.stream is not None:
            self.stream.flush()


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
        self._populate_backend(config)
        self._populate_limits(config)
        self.socket = config.get('general', 'socket')
        self.admin_email = config.get('general', 'admin_email')
        self.service_name = config.get('general', 'service_name')

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

    def _populate_limits(self, config):
        self.limits = {}
        if config.has_option('limits', 'running'):
            self.limits['running'] = config.getint('limits', 'running')
        else:
            self.limits['running'] = 5

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
        sorted_others = ['PREPROCESSING', 'RUNNING', 'POSTPROCESSING',
                         'COMPLETED', 'ARCHIVED']
        # INCOMING and PREPROCESSING directories must be specified
        for key in ('INCOMING', 'PREPROCESSING'):
            others.remove(key)
            self.directories[key] = config.get('directories', key)
        # We should have defaults for each other directory except FAILED
        assert(len(sorted_others) == len(others))
        # Other directories (except EXPIRED) are optional:
        # default to the directory for the previous state
        for n in range(1, len(sorted_others)):
            key = sorted_others[n]
            default_key = sorted_others[n - 1]
            if config.has_option('directories', key):
                self.directories[key] = config.get('directories', key)
            else:
                self.directories[key] = self.directories[default_key]
        # FAILED should default to the COMPLETED directory
        if config.has_option('directories', 'FAILED'):
            self.directories['FAILED'] = config.get('directories', 'FAILED')
        else:
            self.directories['FAILED'] = self.directories['COMPLETED']

    def _populate_backend(self, config):
        self.backend = {}
        self.backend['state_file'] = config.get('backend', 'state_file')
        self.backend['check_minutes'] = config.getint('backend',
                                                      'check_minutes')
        self.backend['user'] = config.get('backend', 'user')

    def _populate_oldjobs(self, config):
        self.oldjobs = {}
        for key in ('archive', 'expire'):
            self.oldjobs[key] = self._get_time_delta(config, 'oldjobs', key)
        archive = self.oldjobs['archive']
        expire = self.oldjobs['expire']
        # archive time must not be greater than expire (None counts as
        # infinity)
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
       a unique `name` (e.g. 'user') and a given `type`
       (e.g. 'VARCHAR(15)'). `null` specifies whether the field can be NULL
       (valid values are True, False, 'YES', 'NO'). `key` if given specifies
       what kind of key it is (e.g. 'PRIMARY' or 'PRI'). `default` specifies
       the default value of the field. If `index` is True, create an index
       on this field (the index gets the same name as the field, except with
       an '_index' suffix)."""

    def __init__(self, name, type, null=True, key=None, default=None,
                 index=False):
        self.name = name
        self.type = type
        # Map MySQL DESCRIBE null types to Python booleans
        if null == 'NO':
            null = False
        if null == 'YES':
            null = True
        # default cannot be NULL if NULL is not allowed for this field
        if not null and default is None:
            default = ''
        # Default cannot be '' for DATETIME fields
        if type == 'DATETIME' and default == '':
            default = None
        # Map MySQL DESCRIBE key type to full name
        if key == 'PRI':
            key = 'PRIMARY'
        if key == '' or key == 'MUL':  # Ignore fields with MySQL INDEX here
            key = None
        self.null = null
        self.key = key
        self.default = default
        self.index = index

    def __eq__(self, other):
        return self.name == other.name and self.type == other.type \
               and self.key == other.key and self.null == other.null \
               and self.default == other.default and self.index == other.index

    def __ne__(self, other):
        return not self == other

    def get_schema(self):
        """Get the SQL schema needed to create a table containing
           this field."""
        schema = self.name + " " + self.type
        if self.key:
            schema += " %s KEY" % self.key
        if not self.null:
            schema += " NOT NULL"
        if self.default is not None:
            schema += " DEFAULT '%s'" % self.default
        return schema


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
        states = ",".join("'%s'" % x for x in _JobState.get_valid_states())
        self.add_field(MySQLField('name', 'VARCHAR(40)', key='PRIMARY',
                                  null=False))
        self.add_field(MySQLField('user', 'VARCHAR(40)'))
        self.add_field(MySQLField('passwd', 'CHAR(10)'))
        self.add_field(MySQLField('contact_email', 'VARCHAR(100)'))
        self.add_field(MySQLField('directory', 'TEXT'))
        self.add_field(MySQLField('url', 'TEXT', null=False))
        self.add_field(MySQLField('state', "ENUM(%s)" % states,
                                  null=False, default='INCOMING', index=True))
        self.add_field(MySQLField('submit_time', 'DATETIME', null=False))
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
        for field in self._fields:
            if field.index:
                c.execute('CREATE INDEX %s_index ON %s (%s)' \
                          % (field.name, self._jobtable, field.name))
        self.conn.commit()

    def _count_all_jobs_in_state(self, state):
        """Return a count of all the jobs in the given job state."""
        c = self.conn.cursor()
        c.execute('SELECT COUNT(*) FROM %s WHERE state=%s' \
                  % (self._jobtable, self._placeholder), (state,))
        return c.fetchone()[0]

    def _get_all_jobs_in_state(self, state, name=None, after_time=None,
                               runner_id=None):
        """Get all the jobs in the given job state, as a generator of
           :class:`Job` objects (or a subclass, as given by the `jobcls`
           argument to the :class:`Database` constructor).
           If `name` is specified, only jobs which match the given name are
           returned.
           If `after_time` is specified, only jobs where the time (given in
           the database column of the same name) is less than the current
           system time are returned.
           If `runner_id` is specified, only jobs which match the given
           runner ID are returned.
        """
        fields = [x.name for x in self._fields]
        query = 'SELECT ' + ', '.join(fields) + ' FROM ' + self._jobtable
        wheres = ['state=' + self._placeholder]
        params = [state]
        if name is not None:
            wheres.append('name=' + self._placeholder)
            params.append(name)
        if runner_id is not None:
            wheres.append('runner_id=' + self._placeholder)
            params.append(runner_id)
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
            metadata = _JobMetadata(fields, row)
            yield self._jobcls(self, metadata, _JobState(state))

    def _delete_job(self, metadata, state):
        """Delete a job from the job state table."""
        c = self.conn.cursor()
        query = 'DELETE FROM ' + self._jobtable \
                + ' WHERE name=' + self._placeholder
        c.execute(query, [metadata['name']])
        self.conn.commit()
        metadata.mark_synced()

    def _update_job(self, metadata, state):
        """Update a job in the job state table."""
        c = self.conn.cursor()
        query = 'UPDATE ' + self._jobtable + ' SET ' \
                + ', '.join(x + '=' + self._placeholder \
                            for x in metadata.keys()) \
                + ' WHERE name=' + self._placeholder
        c.execute(query, metadata.values() + [metadata['name']])
        self.conn.commit()
        metadata.mark_synced()

    def _change_job_state(self, metadata, oldstate, newstate):
        """Change the job state in the database. This has the side effect of
           updating the job (as if :meth:`_update_job` were called)."""
        c = self.conn.cursor()
        query = 'UPDATE ' + self._jobtable + ' SET ' \
                + ', '.join(x + '=' + self._placeholder \
                            for x in metadata.keys() + ['state']) \
                + ' WHERE name=' + self._placeholder
        c.execute(query, metadata.values() + [newstate, metadata['name']])
        self.conn.commit()
        metadata.mark_synced()


class WebService(object):
    """Top-level class used by all web services. Pass in a :class:`Config`
       (or subclass) object for the `config` argument, and a :class:`Database`
       (or subclass) object for the `db` argument.
    """

    #: Version number of the service, or None.
    version = None

    def __init__(self, config, db):
        self.config = config
        self.config._read_db_auth('back')
        self.__delete_state_file_on_exit = False
        self.db = db
        self.db._connect(config)

    def __del__(self):
        if self.__delete_state_file_on_exit:
            os.unlink(self.config.backend['state_file'])

    def get_running_pid(self):
        """Return the process ID of a currently running web service, by
           querying the state file. If no service is running, return None; if
           the last run of the service failed with an unrecoverable error,
           raise a :exc:`StateFileError`."""
        state_file = self.config.backend['state_file']
        try:
            old_state = open(state_file).read().rstrip('\r\n')
        except IOError:
            return
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
            return old_pid
        except OSError:
            return

    def _check_state_file(self):
        """Make sure that a previous run is not still running or encountered
           an unrecoverable error."""
        if self.__delete_state_file_on_exit: # state file checked already
            return
        state_file = self.config.backend['state_file']
        old_pid = self.get_running_pid()
        if old_pid is not None:
            raise StateFileError("A previous run (pid %d) " % old_pid + \
                    "still appears to be running. If this is not the "
                    "case, please manually remove the state "
                    "file (%s)." % state_file)
        self._write_state_file()

    def _write_state_file(self):
        """Write the current PID into the state file"""
        f = open(self.config.backend['state_file'], 'w')
        print >> f, os.getpid()
        self.__delete_state_file_on_exit = True

    def _handle_fatal_error(self, detail):
        err = traceback.format_exc()
        if err is None:
            err = 'Error: ' + str(detail)
        if hasattr(detail, 'original_error'):
            err += "\n\nThis error in turn occurred while trying to " + \
                   "handle the original error below:\n" + detail.original_error
        f = open(self.config.backend['state_file'], 'w')
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
""" % (self.config.service_name, err, self.config.backend['state_file'])
        self.config.send_admin_email(subject, body)
        raise

    def get_job_by_name(self, state, name):
        """Get the job with the given name in the given job state. Returns
           a :class:`Job` object, or None if the job is not found."""
        jobs = list(self.db._get_all_jobs_in_state(state, name=name))
        if len(jobs) == 1:
            return jobs[0]

    def _get_job_by_runner_id(self, runner, runner_id):
        """Get the job with the given runner_id. Returns
           a :class:`Job` object, or None if the job is not found."""
        r = runner._runner_name + ':' + runner_id
        jobs = list(self.db._get_all_jobs_in_state('RUNNING', runner_id=r))
        if len(jobs) == 1:
            return jobs[0]

    def delete_database_tables(self):
        """Delete all tables in the database used to hold job state."""
        self.db._delete_tables()

    def create_database_tables(self):
        """Create all tables in the database used to hold job state."""
        self.db._create_tables()

    def do_all_processing(self, daemonize=False):
        """Process incoming jobs, completed jobs, and old jobs. This method
           will run forever, looping over the available jobs, until the
           web service is killed. If `daemonize` is True, this loop will be
           run as a daemon (subprocess), so that the main program can
           continue."""
        # Check state file before overwriting the socket
        self._check_state_file()
        try:
            self._sanity_check()
            s = self._make_socket()
            if daemonize:
                _make_daemon()
                # Need to update state file with the child PID
                self._write_state_file()
            try:
                try:
                    self._do_periodic_actions(s)
                except _SigTermError:
                    pass # Expected, so just swallow it
            finally:
                self._close_socket(s)
        except Exception, detail:
            self._handle_fatal_error(detail)

    def _sanity_check(self):
        """Do basic sanity checking of the web service"""
        self._filesystem_sanity_check()
        self._job_sanity_check()

    def _job_sanity_check(self):
        """Check for jobs in incorrect states"""
        for job in self.db._get_all_jobs_in_state('PREPROCESSING'):
            job._sanity_check()
        for job in self.db._get_all_jobs_in_state('POSTPROCESSING'):
            job._sanity_check()

    def _filesystem_sanity_check(self):
        """Check that filesystem is consistent with the database"""
        # Get list of all unique directory names for job states
        states = _JobState.get_valid_states()
        states.remove('EXPIRED')
        directories = dict.fromkeys(self.config.directories[x] for x in states)
        # Build a list of all job directories; error out if 'garbage' files
        # are found in any top-level directory
        jobdirs = {}
        garbage = []
        baddirs = []
        for dir in directories:
            if not os.path.isdir(dir):
                baddirs.append(dir)
            for f in glob.glob(os.path.join(dir, '*')):
                if not os.path.isdir(f):
                    garbage.append(f)
                else:
                    jobdirs[f] = None
        if len(baddirs) > 0:
            raise SanityError("The following job directories were not found. "
                              "The service will not function correctly "
                              "without them: %s" % ", ".join(baddirs))
        if len(garbage) > 0:
            raise SanityError("The following files were found in job "
                              "directories. They need to be removed, since "
                              "their presence may interfere with the correct "
                              "operation of the service: %s" \
                              % ", ".join(garbage))

        # Get all jobs from the database for each state
        for state in states:
            for job in self.db._get_all_jobs_in_state(state):
                dir = job.directory
                # Check to make sure directory exists
                if not os.path.exists(dir):
                    raise SanityError("Directory %s for job %s does not "
                                      "exist" % (dir, job.name))
                # Remove from list of filesystem directories
                # Note that we don't ensure that the directory is *in* this
                # list, since if the directories in the configuration file
                # were changed, old jobs may still live in the old locations
                jobdirs.pop(os.path.normpath(dir), None)
        # Check to see if any directories are left that weren't in the db
        if len(jobdirs) > 0:
            raise SanityError("The following directories were found on disk "
                              "that don't have a matching entry in the job "
                              "database. Please remove these directories, "
                              "since their presence may interfere with the "
                              "correct operation of the service: %s" \
                              % ", ".join(jobdirs.iterkeys()))

    def _make_socket(self):
        """Create the socket used by the frontend to talk to us."""
        sockfile = self.config.socket
        try:
            os.unlink(sockfile)
        except OSError:
            pass
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.bind(sockfile)
        s.listen(5)
        # Make it writeable by the web server
        p = subprocess.Popen(['setfacl', '-m', 'u:apache:rwx', sockfile],
                             stderr=subprocess.PIPE)
        err = p.stderr.read()
        ret = p.wait()
        if ret != 0:
            raise OSError("setfacl failed with code %d and stderr %s" \
                          % (ret, err))
        return s

    def _close_socket(self, sock):
        sockfile = self.config.socket
        sock.close()
        os.unlink(sockfile)

    def _get_oldjob_interval(self):
        """Get the time in seconds between checks for expired or archived
           jobs."""
        oldjob_interval = min(self.config.oldjobs['archive'],
                              self.config.oldjobs['expire']) / 10
        return oldjob_interval.seconds + oldjob_interval.days * 24 * 60 * 60

    def _do_periodic_actions(self, sock):
        """Do periodic actions necessary to process jobs. Incoming jobs are
           processed whenever the frontend asks us to (or, failing that,
           every check_minutes); completed jobs are checked for every
           check_minutes; and archived and expired jobs are also
           checked periodically."""
        eq = saliweb.backend.events._EventQueue()
        self._event_queue = eq
        saliweb.backend.events._IncomingJobs(self, sock).start()
        saliweb.backend.events._OldJobs(self).start()

        timeout = self.config.backend['check_minutes'] * 60
        while True:
            # During the get, SIGTERM should cleanly terminate the daemon
            # (clean up state file and socket); at other times, ignore the
            # signal, hopefully so the system stays in a consistent state
            signal.signal(signal.SIGTERM, _sigterm_handler)
            event = eq.get(timeout)
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            if event is None:
                self._process_completed_jobs()
                self._process_incoming_jobs()
            else:
                event.process()

    def _process_incoming_jobs(self):
        """Check for any incoming jobs, and run each one."""
        numrunning = self.db._count_all_jobs_in_state('RUNNING')
        maxrunning = self.config.limits['running']
        # Save doing an extra SQL SELECT if we're already at the maximum
        if numrunning >= maxrunning:
            return
        for job in self.db._get_all_jobs_in_state('INCOMING'):
            job._try_run(self)
            numrunning += 1
            if numrunning >= maxrunning:
                return

    def _process_completed_jobs(self):
        """Check for any jobs that have just completed, and process them."""
        for job in self.db._get_all_jobs_in_state('RUNNING'):
            job._try_complete(self)

    def _process_old_jobs(self):
        """Check for any old job results and archive or delete them."""
        for job in self.db._get_all_jobs_in_state('COMPLETED',
                                                 after_time='archive_time'):
            job._try_archive()
        for job in self.db._get_all_jobs_in_state('ARCHIVED',
                                                  after_time='expire_time'):
            job._try_expire()


class Job(object):
    """Class that encapsulates a single job in the system. Jobs are not
       created by the user directly, but by querying a :class:`WebService`
       object.
    """

    _state_file_wait_time = 5.0
    _runners = {}

    # Note: make sure that all code paths are wrapped with try/except, so that
    # if an exception occurs, it is caught and _fail() is called. Note that
    # some exceptions (e.g. qstat failure) should perhaps be ignored, as they
    # may be transient and do not directly affect the job.

    def __init__(self, db, metadata, state):
        # todo: Sanity check; make sure metadata is OK (if not, call _fail)
        self._db = db
        self._metadata = metadata
        self.__state = state

    @classmethod
    def register_runner_class(cls, runnercls):
        """Maintain a mapping from names to :class:`Runner` classes. If you
           define a :class:`Runner` subclass, you must call this method,
           passing that subclass."""
        exist = cls._runners.get(runnercls._runner_name, None)
        if exist is not None and exist is not runnercls:
            # Runner name must be unique
            raise TypeError("Two Runner classes have the same name (%s): "
                            "%s and %s" % (runnercls._runner_name, exist,
                                           runnercls))
        cls._runners[runnercls._runner_name] = runnercls

    def _get_job_state_file(self):
        return os.path.join(self.directory, 'job-state')

    def get_log_handler(self):
        """Create and return a standard Python log Handler object. By default
           it directs log messages to a file called 'framework.log' in the job
           directory. This can be overridden to send log output elsewhere,
           e.g. in an email. Do not call this method directory; instead use
           :attr:`logger` to access the logger object."""
        filename = os.path.join(self.directory, 'framework.log')
        hdlr = logging.StreamHandler(_DelayFileStream(filename))
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        hdlr.setFormatter(formatter)
        return hdlr

    def _run_in_job_directory(self, meth, *args, **keys):
        """Run a method with the working directory set to the job directory.
           The method can also log by accessing :attr:`logger`.
           Restore the cwd after the method completes."""
        cwd = os.getcwd()
        hdlr = self.get_log_handler()
        self.logger = logging.getLogger(self.service_name)
        self.logger.addHandler(hdlr)
        try:
            os.chdir(self.directory)
            return meth(*args, **keys)
        finally:
            hdlr.flush()
            hdlr.close()
            if hasattr(self, 'logger'):
                self.logger.removeHandler(hdlr)
                del self.logger
            os.chdir(cwd)

    def _frontend_sanity_check(self):
        """Make sure that the frontend set up the job correctly."""
        # SQL schema should not allow this, but check anyway just to be sure:
        if self.name is None:
            raise SanityError("Frontend did not set the job name")
        if self.directory is None:
            raise SanityError("Frontend did not set the directory field in "
                              "the database for job %s" % self.name)
        if not os.path.isdir(self.directory):
            # Set directory to None otherwise _fail() will itself fail, since
            # it won't be able to move the (invalid) directory
            dir = self.directory
            self._metadata['directory'] = None
            self._sync_metadata()
            raise SanityError("Job %s: directory %s is not a directory" \
                              % (self.name, dir))

    def _start_runner(self, runner, webservice):
        """Start up a job using a :class:`Runner` and store the ID."""
        runner_id = runner._runner_name + ':' + runner._run(webservice)
        self._metadata['runner_id'] = runner_id
        self._sync_metadata()

    def _try_run(self, webservice):
        """Take an incoming job and try to start running it."""
        try:
            self._frontend_sanity_check()
            self._metadata['preprocess_time'] = datetime.datetime.utcnow()
            self._set_state('PREPROCESSING')
            # Delete job-state file, if present from a previous run
            try:
                os.unlink(self._get_job_state_file())
            except OSError:
                pass
            self.__skip_run = False
            self._run_in_job_directory(self.preprocess)
            if self.__skip_run:
                self._sync_metadata()
                self._mark_job_completed()
            else:
                self._metadata['run_time'] = datetime.datetime.utcnow()
                self._set_state('RUNNING')
                runner = self._run_in_job_directory(self.run)
                self._start_runner(runner, webservice)
        except Exception, detail:
            self._fail(detail)

    def _sanity_check(self):
        """Check for obvious problems with any job"""
        try:
            state = self._get_state()
            # These states are transient and so jobs should not be found in the
            # database in this state
            if state == 'PREPROCESSING' or state == 'POSTPROCESSING':
                raise SanityError("Job %s is in state %s; this should not be "
                                  "possible unless the web service were shut "
                                  "down uncleanly" % (self.name, state))
        except Exception, detail:
            self._fail(detail)

    def _job_state_file_done(self):
        """Return True only if the job-state file indicates the job
           finished."""
        try:
            f = open(self._get_job_state_file())
            return f.read().rstrip('\r\n') == 'DONE'
        except IOError:
            return False   # if the file does not exist, job is still running

    def _runner_done(self):
        """Return True if the job's :class:`Runner` indicates the job finished,
           or None if that cannot be determined."""
        runner_id = self._metadata['runner_id']
        runner_name, jobid = runner_id.split(':', 1)
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
                 % (self._metadata['runner_id'], self._metadata['directory']))
        return False

    def _try_complete(self, webservice, run_exception=None):
        """Take a running job, see if it completed, and if so, process it."""
        try:
            self._assert_state('RUNNING')
            if not self._has_completed():
                return
            # If the Runner caught an exception, raise it here
            if run_exception is not None:
                raise run_exception
            # Delete job-state file; no longer needed
            os.unlink(self._get_job_state_file())
            self._metadata['postprocess_time'] = datetime.datetime.utcnow()
            self._set_state('POSTPROCESSING')
            self.__reschedule_run = False
            self._run_in_job_directory(self.postprocess)
            if self.__reschedule_run:
                self._set_state('RUNNING')
                runner = self._run_in_job_directory(self.rerun,
                                                    self.__reschedule_data)
                self._start_runner(runner, webservice)
            else:
                self._mark_job_completed()
        except Exception, detail:
            self._fail(detail)

    def _mark_job_completed(self):
        endtime = datetime.datetime.utcnow()
        self._metadata['end_time'] = endtime
        archive_time = self._db.config.oldjobs['archive']
        if archive_time is not None:
            archive_time = endtime + archive_time
        expire_time = self._db.config.oldjobs['expire']
        if expire_time is not None:
            expire_time = endtime + expire_time
        self._metadata['archive_time'] = archive_time
        self._metadata['expire_time'] = expire_time
        self._set_state('COMPLETED')
        self._run_in_job_directory(self.complete)
        self._sync_metadata()
        self.send_job_completed_email()

    def _try_archive(self):
        try:
            self._set_state('ARCHIVED')
            self._run_in_job_directory(self.archive)
            self._sync_metadata()
        except Exception, detail:
            self._fail(detail)

    def _try_expire(self):
        try:
            self._set_state('EXPIRED')
            self.expire()
            self._sync_metadata()
        except Exception, detail:
            self._fail(detail)

    def _sync_metadata(self):
        """If the job metadata has changed, sync the database with it."""
        if self._metadata.needs_sync():
            self._db._update_job(self._metadata, self._get_state())

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
            shutil.rmtree(self._metadata['directory'])
            self._metadata['directory'] = None
        elif self._metadata['directory'] is not None:
            # move job to different directory if necessary
            directory = os.path.join(self._db.config.directories[state],
                                     self.name)
            directory = os.path.normpath(directory)
            if directory != self._metadata['directory']:
                shutil.move(self._metadata['directory'], directory)
                self._metadata['directory'] = directory
        self._db._change_job_state(self._metadata, oldstate, state)

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
            self._metadata['failure'] = reason
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
        # Wake up the web service and let it know a new incoming job is present
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(self._db.config.socket)
            s.send("INCOMING %s" % self.name)
            s.close()
        except socket.error:
            pass

    def delete(self):
        """Delete the job directory and database row."""
        if self._metadata['directory']:
            shutil.rmtree(self._metadata['directory'])
        self._db._delete_job(self._metadata, self._get_state())
        self._metadata = None

    def run(self):
        """Run the job, e.g. on an SGE cluster.
           Must be implemented by the user for each web service; it should
           create and return a suitable :class:`Runner` instance.
           For example, this could generate a simple script and pass it to
           an :class:`SGERunner` instance.
           This method should never be called directly; it is automatically
           called by the backend when needed. To run a new job,
           call :meth:`reschedule_run` instead.
        """

    def rerun(self, data):
        """Run a rescheduled job (if :meth:`postprocess` called
           :meth:`reschedule_run` to run a new job). `data` is a Python object
           passed from the :meth:`reschedule_run` method.
           Like :meth:`run`, this should create and return a suitable
           :class:`Runner` instance.

           By default, this method simply discards `data` and calls the regular
           :meth:`run` method. You can redefine this method if you want to do
           something different for rescheduled runs.
        """
        return self.run()

    def send_user_email(self, subject, body):
        """Email the owner of the job, if requested, with the given `subject`
           and `body`."""
        if self._metadata['contact_email']:
            self._db.config.send_email(self._metadata['contact_email'],
                                       subject, body)

    def complete(self):
        """This method is called after a job completes. Does nothing by
           default, but can be overridden by the user.
           This method should not be called directly."""

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
           the user to compress files, etc.
           This method should not be called directly."""

    def expire(self):
        """Do any necessary processing when an old completed job reaches its
           archive time. Does nothing by default, but can be overridden by
           the user to mail the admin, etc.
           This method should not be called directly."""

    def preprocess(self):
        """Do any necessary preprocessing before the job is actually run.
           Does nothing by default. Note that a user-defined preprocess method
           can call :meth:`skip_run` to skip running of the job on the cluster,
           if it is determined in preprocessing that a job run is not
           necessary.
           This method should not be called directly."""

    def skip_run(self):
        """Tell the backend to skip the actual running of the job, so that
           when preprocessing has completed, it moves directly to the
           COMPLETED state, skipping RUNNING and POSTPROCESSING.

           It is only valid to call this method from the PREPROCESSING state,
           usually from a user-defined :meth:`preprocess` method."""
        self._assert_state('PREPROCESSING')
        self.__skip_run = True

    def postprocess(self):
        """Do any necessary postprocessing when the job completes successfully.
           Does nothing by default. Note that a user-defined postprocess method
           can call :meth:`reschedule_run` to request that the backend runs
           a new cluster job if necessary.
           This method should not be called directly."""

    def reschedule_run(self, data=None):
        """Tell the backend to schedule another job to be run on the cluster
           once postprocessing is complete (the job moves from the
           POSTPROCESSING state back to RUNNING).

           It is only valid to call this method from the POSTPROCESSING state,
           usually from a user-defined :meth:`postprocess` method.

           The rescheduled job is run by calling the :meth:`rerun` method,
           which is passed the `data` Python object (if any).

           Note that because the rescheduled job itself will be postprocessed
           once finished, you must be careful not to create an infinite
           loop here. This could be done by using a file in the job directory
           or a custom field in the job database to prevent a job from being
           rescheduled more than a certain number of times, and/or to pass
           state to the :meth:`postprocess` method (so that it knows it is
           postprocessing a rescheduled job rather than the first job)."""
        self._assert_state('POSTPROCESSING')
        self.__reschedule_run = True
        self.__reschedule_data = data

    name = property(lambda x: x._metadata['name'],
                    doc="Unique job name (read-only)")
    url = property(lambda x: x._metadata['url'],
                   doc="URL containing job results (read-only)")
    service_name = property(lambda x: x._db.config.service_name,
                            doc="Web service name (read-only)")
    directory = property(lambda x: x._metadata['directory'],
                         doc="Current job working directory (read-only)")


class _LockedJobDict(object):
    """A dictionary of job IDs which can be accessed by multiple threads"""
    def __init__(self):
        self._lock = threading.Lock()
        self._dict = {}
    def __contains__(self, key):
        self._lock.acquire()
        ret = key in self._dict
        self._lock.release()
        return ret
    def add(self, key):
        self._lock.acquire()
        try:
            self._dict[key] = None
        finally:
            self._lock.release()
    def remove(self, key):
        self._lock.acquire()
        try:
            del self._dict[key]
        finally:
            self._lock.release()


class Runner(object):
    """Base class for runners, which handle the actual running of a job,
       usually on an SGE cluster (see the :class:`SGERunner` and
       :class:`SaliSGERunner` subclasses). To create a subclass, you must
       implement both a _run method and a _check_completed class method,
       set the _runner_name attribute to a unique name for this class,
       and call :meth:`Job.register_runner_class` passing this class."""


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
    _drmaa = None
    _env = {'SGE_CELL': 'qb3',
            'SGE_ROOT': '/ccpr1/sge6',
            'SGE_QMASTER_PORT': '536',
            'SGE_EXECD_PORT': '537',
            'DRMAA_LIBRARY_PATH':
                    '/ccpr1/sge6/lib/lx24-amd64/libdrmaa.so.1.0'}

    _arch = 'lx24-amd64'
    _waited_jobs = _LockedJobDict()

    def __init__(self, script, interpreter='/bin/sh'):
        Runner.__init__(self)
        self._opts = ''
        self._script = script
        self._interpreter = interpreter
        self._directory = os.getcwd()

    def set_sge_options(self, opts):
        """Set the SGE options to use, as a string,
           for example '-N foo -l mydisk=1G'
        """
        self._opts = opts

    @classmethod
    def _get_drmaa(cls):
        if cls._drmaa is None:
            cls._drmaa = saliweb.backend.sge._DRMAAWrapper(cls._env)
        return cls._drmaa.module, cls._drmaa.session

    def _run(self, webservice):
        """Generate an SGE script in the job directory and run it.
           Return the SGE job ID."""
        script = os.path.join(self._directory, 'sge-script.sh')
        fh = open(script, 'w')
        self._write_sge_script(fh)
        fh.close()
        return self._qsub(script, webservice)

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

    def _qsub(self, script, webservice):
        """Submit a job script to the cluster using DRMAA."""
        drmaa, s = self._get_drmaa()
        jt = s.createJobTemplate()
        # Note that "-w n" turns off verification of -l options, since SGE 6.1
        # always fails at this step (a bug); "-b no" parses the script for
        # additional SGE options
        jt.nativeSpecification = self._opts + ' -w n -b no'
        jt.remoteCommand = script
        jt.workingDirectory = self._directory
        tasks = saliweb.backend.sge._SGETasks(self._opts)
        if tasks:
            jobids = s.runBulkJobs(jt, tasks.first, tasks.last, tasks.step)
            runid = tasks.get_run_id(jobids)
        else:
            runid = s.runJob(jt)
            jobids = [runid]
        s.deleteJobTemplate(jt)
        saliweb.backend.sge._DRMAAJobWaiter(webservice, jobids,
                                            self, runid).start()
        return runid

    @classmethod
    def _check_completed(cls, jobid):
        """Return True if SGE reports that the given job has finished, False
           if it is still running, or None if the status cannot be determined.
        """
        if jobid in cls._waited_jobs:
            return False
        else:
            drmaa, s = cls._get_drmaa()
            try:
                x = s.jobStatus(jobid)
                return False
            except drmaa.InvalidJobException:
                return True
Job.register_runner_class(SGERunner)


class SaliSGERunner(SGERunner):
    """Run commands on the Sali SGE cluster instead of the QB3 cluster."""
    _runner_name = 'salisge'
    _drmaa = None
    _env = {'SGE_CELL': 'sali',
            'SGE_ROOT': '/home/sge61',
            'DRMAA_LIBRARY_PATH':
                        '/home/sge61/lib/lx24-amd64/libdrmaa.so.1.0'}

    _waited_jobs = _LockedJobDict()
Job.register_runner_class(SaliSGERunner)


class _LocalJobWaiter(_JobThread):
    """Wait for a job started by LocalRunner to finish"""
    def __init__(self, webservice, subproc, runner, runid):
        _JobThread.__init__(self, webservice)
        self._subproc = subproc
        self._runner = runner
        self._runid = runid

    def run(self):
        self._runner._waited_jobs.add(self._runid)
        try:
            ret = self._subproc.wait()
            if ret != 0:
                result = OSError("Process failed with return code %d" % ret)
            else:
                result = None
            e = saliweb.backend.events._CompletedJobEvent(self._webservice,
                                                          self._runner,
                                                          self._runid, result)
            self._webservice._event_queue.put(e)
        finally:
            self._runner._waited_jobs.remove(self._runid)


class LocalRunner(Runner):
    """Run a program (given as a list of arguments or a single string) on
       the local machine.

       The program must create a file called job-state in the working
       directory, to contain just the simple text "STARTED" (without the
       quotes) when the job starts and just "DONE" when it completes.
    """

    _runner_name = 'local'
    _waited_jobs = _LockedJobDict()

    def __init__(self, cmd):
        Runner.__init__(self)
        self._cmd = cmd

    def _run(self, webservice):
        """Run the command and return a unique job ID."""
        p = subprocess.Popen(self._cmd, shell=not isinstance(self._cmd, list))
        runid = str(p.pid)
        _LocalJobWaiter(webservice, p, self, runid).start()
        return runid

    @classmethod
    def _check_completed(cls, jobid):
        """Return True if the process has finished or False if it is still
           running."""
        # If the process was not started by us, check for the pid
        if jobid in cls._waited_jobs:
            return False
        else:
            return not os.path.exists("/proc/%s" % jobid)
Job.register_runner_class(LocalRunner)
