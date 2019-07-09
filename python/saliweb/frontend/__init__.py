import flask
from flask import url_for, Markup
import datetime
import ConfigParser
import os
import re
import logging.handlers
import MySQLdb
from .submit import IncomingJob
import saliweb.frontend.config


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
        for k in ('name', 'submit_time', 'state', 'user', 'url'):
            setattr(self, k, sql_dict[k])

    @property
    def name_link(self):
        """Get job name, linked to results page if user is logged in"""
        if flask.g.user and self.user == flask.g.user.name:
            return Markup('<a href="%s">%s</a>' % (self.url, self.name))
        else:
            return self.name


class CompletedJob(object):
    """A job that has completed. Use :func:`get_completed_job` to create
       such a job from a URL."""

    def __init__(self, sql_dict):
        for k in ('name', 'passwd', 'archive_time', 'directory'):
            setattr(self, k, sql_dict[k])
        self._record_results = None

    def get_results_file_url(self, fname):
        """Return a URL which the user can use to download the passed file.
           The file must be in the job directory (or a subdirectory of it);
           absolute paths are not allowed.
           If files are compressed with gzip, the .gz extension can be
           ommitted here if desired. (If it is ommitted, the file will be
           automatically decompressed when the user downloads it; otherwise
           the original .gz file is downloaded.)"""
        url = url_for('results_file', name=self.name, fp=fname,
                       passwd=self.passwd,
                       _external=self._record_results is not None)
        if self._record_results is not None:
            self._record_results.append({'url': url, 'fname': fname})
        return url

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

    # Set defaults for all web services
    app.config.from_object(saliweb.frontend.config)

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


def _get_servers_cookie_info():
    """Get the sali-servers login cookie if available, as a dict"""
    c = flask.request.cookies.get('sali-servers')
    if c:
        c = c.split('&')
        cd = {}
        while len(c) >= 2:
            val = c.pop()
            cd[c.pop()] = val
        return cd


class LoggedInUser(object):
    """Information about the logged-in user.
       `g.user` is set to an instance of this class, or None if no user
       is logged in."""

    #: The name of the user
    name = None

    #: The contact email address of the user
    email = None

    def __init__(self, name, email):
        self.name, self.email = name, email


def _get_logged_in_user():
    """Return a LoggedInUser object for the currently logged-in user, or None"""
    # Make sure logins are SSL-secured
    if flask.request.scheme != 'https':
        return
    c = _get_servers_cookie_info()
    if (c and 'user_name' in c and 'session' in c
        and c['user_name'] != 'Anonymous'):
        dbh = get_db()
        cur = dbh.cursor()
        cur.execute('SELECT email FROM servers.users WHERE user_name=%s '
                    'AND password=%s', (c['user_name'], c['session']))
        row = cur.fetchone()
        if row:
            return LoggedInUser(c['user_name'], row[0])


class Parameter(object):
    """Represent a single parameter (with help). This is used to provide
       help to users of the REST API. See :func:`make_application`.

       :param str name: The name (must match that of the form item).
       :param str description: Help text about the parameter and its use.
       :param bool optional: Whether the parameter can be omitted.
    """
    _xml_type = 'string'

    def __init__(self, name, description, optional=False):
        self._name, self._description = name, description
        self._optional = optional


class FileParameter(Parameter):
    """Represent a single file upload parameter (with help).
       See :class:`Parameter`.
    """
    _xml_type = 'file'


def make_application(name, config, version, parameters=[],
                     static_folder='html', *args, **kwargs):
    """Make and return a new Flask application.

       :param str name: Name of the Python file that owns the app. This should
              normally be `__name__`.
       :param str config: Path to the web service configuration file.
       :param str version: Current version of the web service.
       :param list parameters: The form parameters accepted by the 'submit'
              page. This should be a list of :class:`Parameter` and/or
              :class:`FileParameter` objects, and is used to provide help
              for users of the REST API.
       :return: A new Flask application.

       .. note:: Any additional arguments are passed to the Flask constructor.
    """
    app = flask.Flask(name, *args, static_folder=static_folder, **kwargs)
    _read_config(app, config)
    app.config['VERSION'] = version
    app.config['PARAMETERS'] = parameters
    _setup_email_logging(app)
    app.register_blueprint(_blueprint)

    @app.errorhandler(_ResultsError)
    def handle_results_error(error):
        ext = 'xml' if _request_wants_xml() else 'html'
        return (flask.render_template('saliweb/results_error.%s' % ext,
                                      message=str(error)), error.http_status)

    @app.errorhandler(_UserError)
    def handle_user_error(error):
        ext = 'xml' if _request_wants_xml() else 'html'
        return (flask.render_template('saliweb/user_error.%s' % ext,
                                      message=str(error)), error.http_status)

    @app.before_request
    def check_login():
        flask.g.user = _get_logged_in_user()

    @app.teardown_appcontext
    def close_db(error):
        if hasattr(flask.g, 'db_conn'):
            flask.g.db_conn.close()

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
    """Create and return a new :class:`CompletedJob` for a given URL.
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
    elif job_row['state'] in ('EXPIRED', 'ARCHIVED'):
        raise _ResultsGoneError("Results for job '%s' are no "
                                "longer available for download" % name)
    elif job_row['state'] != 'COMPLETED':
        raise _ResultsStillRunningError(
            "Job '%s' has not yet completed; please check back later" % name)
    return CompletedJob(job_row)


def _request_wants_xml():
    """Return True if the client asked for XML output rather than HTML.
       This is done by adding the HTTP header `Accept: application/xml`
       to the request, and is typically used in the REST API."""
    accept = flask.request.accept_mimetypes
    best = accept.best_match(['application/xml', 'text/html'])
    return best == 'application/xml' and accept[best] > accept['text/html']


def render_queue_page():
    """Return an HTML list of all jobs. Typically used in the `/job` route for
       a GET request."""
    # The /job endpoint is used by the old Perl REST API, so reuse it here
    # for help on the REST API.
    if _request_wants_xml():
        return flask.render_template('saliweb/help.xml')
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
       If the address is invalid, raise an :exc:`InputValidationError`
       exception.

       :param str email: The email address to check.
       :param bool required: If True, an empty email address will also result
              in an exception (usually it is recommended that the email address
              is optional).
    """
    if not email and not required:
        return
    elif (not email
          or not re.match(r'[\w\.-]+@[\w-]+\.[\w-]+((\.[\w-]+)*)?$', email)):
        raise InputValidationError(
            "Please provide a valid return email address")


def check_modeller_key(modkey):
    """Check a provided MODELLER key.
       If the key is empty or invalid, raise an
       :exc:`InputValidationError` exception.

       :param str modkey: The MODELLER key to check.
    """
    if modkey != flask.current_app.config['MODELLER_LICENSE_KEY']:
        raise InputValidationError(
            "You have entered an invalid MODELLER key: " + str(modkey))


def render_results_template(template_name, job, **context):
    """Render a template for the job results page.
       This normally functions like `flask.render_template` but will instead
       return XML if the user requests it (for the REST API)."""
    if _request_wants_xml():
        job._record_results = []
    r = flask.render_template(template_name, job=job, **context)
    if job._record_results is not None:
        return flask.render_template('saliweb/results.xml',
                                     results=job._record_results)
    else:
        return r


def render_submit_template(template_name, job, **context):
    """Render a template for the job submission page.
       This normally functions like `flask.render_template` but will instead
       return XML if the user requests it (for the REST API)."""
    if _request_wants_xml():
        return flask.render_template('saliweb/submit.xml', job=job)
    else:
        return flask.render_template(template_name, job=job, **context)
