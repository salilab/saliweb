import re
import os
import flask
import random
import socket
import fcntl
import string
import sys
import datetime


def _get_job_directory(job_name):
    """Get the full path to the incoming directory for the given job name"""
    config = flask.current_app.config
    return os.path.join(config['DIRECTORIES_INCOMING'], job_name)


def _sanitize_job_name(job_name):
    """Return a safe version of the user-provided job name"""
    # Provide default
    job_name = job_name or datetime.date.today().strftime("job%Y%m%d")
    # Remove potentially dodgy characters in job_name
    job_name = re.sub('[^a-zA-Z0-9_-]', '', job_name)
    # Make sure job_name fits in the db (plus extra space for
    # auto-generated suffix if needed)
    return job_name[:30]


def _get_trial_job_names(user_job_name):
    """Get a list of possible job names given a user-provided value"""
    user_job_name = _sanitize_job_name(user_job_name)
    yield user_job_name
    for trial in range(50):
        yield "%s_%d%d" % (user_job_name, random.randint(0, 100000), trial)


def _try_job_name(job_name, cur):
    """Determine if a new job name is acceptable and unique. If it is, return
       the job directory; otherwise, return None"""
    def is_job_in_db():
        cur.execute("SELECT COUNT(name) FROM jobs WHERE name=%s", (job_name,))
        return cur.fetchone()[0] > 0

    job_dir = _get_job_directory(job_name)
    if not os.path.exists(job_dir) and not is_job_in_db():
        try:
            os.mkdir(job_dir)
        except FileExistsError:
            # Directory may have been made between exists() check and mkdir()
            return None
        if not is_job_in_db():  # avoid race condition
            return job_dir


def _get_job_name_directory(user_job_name):
    """Given a user-provided name, return the canonical job name
       and directory"""
    from . import get_db

    dbh = get_db()
    cur = dbh.cursor()
    for job_name in _get_trial_job_names(user_job_name):
        job_dir = _try_job_name(job_name, cur)
        if job_dir:
            return job_name, job_dir
    raise ValueError("Could not determine a unique job name")


def _generate_random_password(length):
    """Generate a random alphanumeric password of the given length"""
    valid = string.ascii_lowercase + string.ascii_uppercase + string.digits
    return ''.join(random.choice(valid) for _ in range(length))


def _generate_results_url(job_name, force_xml=False):
    passwd = _generate_random_password(10)
    kwargs = {}
    if force_xml:
        kwargs['force_xml'] = '1'
    # _external=True gives us a full URL (url_for usually returns a
    # relative URL)
    url = flask.url_for("results", name=job_name, passwd=passwd,
                        _external=True, **kwargs)
    return url, passwd


class IncomingJob(object):
    """Represents a new job that is being submitted to the backend.
       Each new job has a unique name and a directory into which input files
       can be placed. Once all input files are in place, :meth:`submit`
       should be called to submit the job to the backend.

       :param str given_name: A user-provided name for the job."""

    _url = None

    #: The name of the job. Note that this is not necessarily the same
    #: as the name given by the user, since it must be unique, and fit in our
    #: database schema. (The user-provided name is thus sanitized if necessary
    #: and a unique suffix added.)
    name = None

    #: The directory on disk for this job. Input files should be placed in this
    #: directory prior to calling :meth:`submit`.
    directory = None

    # todo: cleanup if submit() didn't get called
    def __init__(self, given_name=None):
        self.name, self.directory = _get_job_name_directory(given_name)
        self._submitted = False
        _add_incoming_job(self)

    def get_path(self, fname):
        """Get the full path to a file in the job's directory.

           :param str fname: The file name
           :return: Full path to the file in the job's directory.
        """
        return os.path.join(self.directory, fname)

    @property
    def results_url(self):
        """The URL where this job's results will be found when it is complete.
           This is only filled in when :meth:`submit` is called."""
        if self._url:
            return self._url
        else:
            raise ValueError("Cannot get results URL before job is submitted")

    def submit(self, email=None, force_results_xml=False):
        """Submits the job to the backend to run on the cluster.
           If an email address is provided, it is notified when the
           job completes.
           If `force_results_xml` is True, `force_xml=True` is passed to
           the results URL, which can be used to force XML output even without
           the HTTP Accept header being set (used for backwards
           compatibility)."""

        from . import get_db

        dbh = get_db()
        config = flask.current_app.config
        user = flask.g.user.name if flask.g.user else None

        self._url, self._passwd = _generate_results_url(self.name,
                                                        force_results_xml)

        # Insert row into database table
        cur = dbh.cursor()
        if config.get('TRACK_HOSTNAME'):
            cur.execute("INSERT INTO jobs (name,passwd,user,contact_email,"
                        "directory,url,hostname,submit_time) VALUES(%s, %s, "
                        "%s, %s, %s, %s, %s, UTC_TIMESTAMP())",
                        (self.name, self._passwd, user, email, self.directory,
                         self._url, flask.request.remote_addr))
        else:
            cur.execute("INSERT INTO jobs (name,passwd,user,contact_email,"
                        "directory,url,submit_time) VALUES(%s, %s, "
                        "%s, %s, %s, %s, UTC_TIMESTAMP())",
                        (self.name, self._passwd, user, email, self.directory,
                         self._url))
        dbh.commit()

        self._submitted = True
        self._inform_backend(config)

    def _inform_backend(self, config):
        """Use socket to inform backend of new incoming job"""
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            s.connect(config['SOCKET'])
        except socket.error:
            return  # skip if backend is not running
        fcntl.flock(s, fcntl.LOCK_EX)
        try:
            ss = "INCOMING %s\n" % self.name
            if sys.version_info[0] >= 3:
                ss = ss.encode('utf-8')
            s.sendall(ss)
        except socket.error:
            pass  # ignore broken pipe errors
        fcntl.flock(s, fcntl.LOCK_UN)
        s.close()


def _add_incoming_job(job):
    """Keep track of all incoming jobs, so we can clean up failed ones"""
    if not hasattr(flask.g, 'incoming_jobs'):
        flask.g.incoming_jobs = []
    flask.g.incoming_jobs.append(job)
