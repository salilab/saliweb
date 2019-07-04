import flask
from flask import url_for, Markup
import datetime
import ConfigParser
import os
import re
import logging.handlers
import MySQLdb


class _UserError(Exception):
    """An error that is caused by the user and should be reported"""
    pass


class InputValidationError(_UserError):
    """Invalid user input, usually during a job submission.
       These errors are handled by reporting them to the user and asking
       them to fix their input accordingly."""
    http_status = 400  # bad request


class _ResultsError(Exception):
    pass


class _ResultsBadJobError(_ResultsError):
    http_status = 400  # bad request


class _ResultsGoneError(_ResultsError):
    http_status = 410  # gone


class _ResultsStillRunningError(_ResultsError):
    http_status = 503


def _format_timediff(timediff):
    def _format_unit(df, unit):
        return '%d %s%s' % (df, unit, '' if unit == 1 else 's')

    if not timediff:
        return
    timediff = timediff - datetime.datetime.utcnow()
    try:
        diff_sec = timediff.total_seconds()
    except AttributeError:  # python 2.6
        diff_sec = timediff.days * 24*60*60 + timediff.seconds
    if diff_sec < 0:
        return
    if diff_sec < 120:
        return _format_unit(diff_sec, 'second')
    diff_sec /= 60.0
    if diff_sec < 120:
        return _format_unit(diff_sec, 'minute')
    diff_sec /= 60.0
    if diff_sec < 48:
        return _format_unit(diff_sec, 'hour')
    diff_sec /= 24.0
    return _format_unit(diff_sec, 'day')


class _QueuedJob(object):
    """A job that is in the job queue"""
    def __init__(self, sql_dict):
        for k in ('name', 'submit_time', 'state'):
            setattr(self, k, sql_dict[k])


class CompletedJob(object):
    """A job that has completed. Use :func:`get_completed_job` to create
       such a job from a URL."""

    def __init__(self, sql_dict):
        for k in ('name', 'passwd', 'archive_time', 'directory'):
            setattr(self, k, sql_dict[k])

    def get_results_file_url(self, fname):
        """Return a URL which the user can use to download the passed file.
           The file must be in the job directory (or a subdirectory of it);
           absolute paths are not allowed.
           If files are compressed with gzip, the .gz extension can be
           ommitted here if desired. (If it is ommitted, the file will be
           automatically decompressed when the user downloads it; otherwise
           the original .gz file is downloaded.)"""
        return url_for('results_file', name=self.name, fp=fname,
                       passwd=self.passwd)

    def get_results_available_time(self):
        """Get an HTML fragment stating how long results will be available"""
        avail = _format_timediff(self.archive_time)
        if avail:
            return Markup('<p>Job results will be available at this '
                          'URL for %s.</p>' % avail)


_blueprint = flask.Blueprint('saliweb', __name__, template_folder='templates')


def _read_config(app, fname):
    """Read the webservice configuration file and set Flask-style app.config
       from it. Flask config names are all uppercase and have the config
       section (except for [general]) prefixed."""
    config = ConfigParser.SafeConfigParser()

    with open(fname) as fh:
        config.readfp(fh, fname)

    for section in config.sections():
        prefix = '' if section == 'general' else section.upper() + '_'
        for name, value in config.items(section):
            app.config[prefix + name.upper()] = value

    config_dir = os.path.dirname(os.path.abspath(fname))
    frontend_db = config.get('database', 'frontend_config')
    fname = os.path.join(config_dir, frontend_db)
    with open(fname) as fh:
        config.readfp(fh, fname)
    for name in ('user', 'passwd'):
        value = config.get('frontend_db', name)
        app.config["DATABASE_" + name.upper()] = value

    # Set defaults
    if 'DATABASE_SOCKET' not in app.config:
        app.config['DATABASE_SOCKET'] = '/var/lib/mysql/mysql.sock'


def _setup_email_logging(app):
    if not app.debug:
        mail_handler = logging.handlers.SMTPHandler(
            mailhost=('localhost', 25),
            fromaddr='no-reply@modbase.compbio.ucsf.edu',
            toaddrs=[app.config['ADMIN_EMAIL']],
            subject='%s web service error' % app.config['SERVICE_NAME'])
        mail_handler.setLevel(logging.ERROR)
        app.logger.addHandler(mail_handler)


def make_application(name, config, version, static_folder='html', *args,
                     **kwargs):
    """Make and return a new Flask application.

       :param str name: Name of the Python file that owns the app. This should
              normally be `__name__`.
       :param str name: Path to the web service configuration file.
       :param str version: Current version of the web service.
       :return: A new Flask application.

       .. note:: Any additional arguments are passed to the Flask constructor.
    """
    app = flask.Flask(name, *args, static_folder=static_folder, **kwargs)
    _read_config(app, config)
    app.config['VERSION'] = version
    _setup_email_logging(app)
    app.register_blueprint(_blueprint)

    @app.errorhandler(_ResultsError)
    def handle_results_error(error):
        return (flask.render_template('saliweb/results_error.html',
                                      message=str(error)), error.http_status)

    @app.errorhandler(_UserError)
    def handle_user_error(error):
        return (flask.render_template('saliweb/user_error.html',
                                      message=str(error)), error.http_status)

    return app


def get_db():
    """Get the MySQL database connection"""
    if not hasattr(flask.g, 'db_conn'):
        app = flask.current_app
        flask.g.db_conn = MySQLdb.connect(user=app.config['DATABASE_USER'],
            db=app.config['DATABASE_DB'],
            unix_socket=app.config['DATABASE_SOCKET'],
            passwd=app.config['DATABASE_PASSWD'])
    return flask.g.db_conn


def get_completed_job(name, passwd):
    """Create an return a new :class:`CompletedJob` for a given URL.
       If the job is not valid (e.g. incorrect password) an exception is
       raised.

       :param str name: The name of the job.
       :param str passwd: Password for the job.
       :return: A new CompletedJob.
       :rtype: :class:`CompletedJob`
    """
    conn = get_db()
    c = MySQLdb.cursors.DictCursor(conn)
    c.execute('SELECT * FROM jobs WHERE name=%s AND passwd=%s', (name, passwd))
    job_row = c.fetchone()
    if not job_row:
        raise _ResultsBadJobError('Job does not exist, or wrong password')
    else:
        if job_row['state'] in ('EXPIRED', 'ARCHIVED'):
            raise _ResultsGoneError("Results for job '%s' are no "
                                    "longer available for download" % name)
        else:
            if job_row['state'] != 'COMPLETED':
                raise _ResultsStillRunningError(
                    "Job '%s' has not yet completed; please check back later"
                    % name)
    return CompletedJob(job_row)


def render_queue_page():
    """Display a list of all jobs. Typically used in the `/job` route for
       a GET request."""
    conn = get_db()
    c = MySQLdb.cursors.DictCursor(conn)
    c.execute("SELECT * FROM jobs WHERE state != 'ARCHIVED' "
              "AND state != 'EXPIRED' AND state != 'COMPLETED' "
              "ORDER BY submit_time DESC")
    running_jobs = [ _QueuedJob(x) for x in c ]
    c.execute("SELECT * FROM jobs WHERE state='COMPLETED' "
              "ORDER BY submit_time DESC")
    completed_jobs = [ _QueuedJob(x) for x in c ]
    return flask.render_template('saliweb/queue.html',
                                 running_jobs=running_jobs,
                                 completed_jobs=completed_jobs)


def check_email(email, required=False):
    """Check a user-provided email address for sanity.

       :param str email: The email address to check.
       :param bool required: If True, an empty email address will raise
              an exception (usually it is recommended that the email address
              is optional).
    """
    if not email and not required:
        return
    elif (not email
          or not re.match(r'[\w\.-]+@[\w-]+\.[\w-]+((\.[\w-]+)*)?$', email)):
        raise InputValidationError(
            "Please provide a valid return email address")


def _get_modeller_key():
    return "@MODELLERKEY@"


def check_modeller_key(modkey):
    """Check a provided MODELLER key.
       If the key is empty or invalid, throw an
       :exc:`InputValidationError` exception.

       :param str modkey: The MODELLER key to check.
    """
    if modkey != _get_modeller_key():
        raise InputValidationError(
            "You have entered an invalid MODELLER key: " + str(modkey))
