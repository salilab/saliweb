import flask
from flask import url_for
from markupsafe import Markup
import datetime
import configparser
import os
import sys
import re
import logging.handlers
import shutil
import gzip
import MySQLdb
import MySQLdb.cursors
from .submit import IncomingJob  # noqa: F401
import saliweb.frontend.config


class _UserError(Exception):
    """An error that is caused by the user and should be reported"""
    pass


class InputValidationError(_UserError):
    """Invalid user input, usually during a job submission.
       These errors are handled by reporting them to the user and asking
       them to fix their input accordingly."""
    http_status = 400  # bad request


class AccessDeniedError(Exception):
    """Attempt by the user to access a protected page. These errors
       can be raised by any page and are generally handled by displaying
       an HTML/XML error page."""
    http_status = 401  # unauthorized


class _ResultsError(Exception):
    pass


class _ResultsBadJobError(_ResultsError):
    http_status = 400  # bad request


class _ResultsGoneError(_ResultsError):
    http_status = 410  # gone


class _ResultsStillRunningError(_ResultsError):
    http_status = 503

    def __init__(self, msg, job, template):
        super(_ResultsStillRunningError, self).__init__(msg)
        self.job = job
        self.template = template


def _format_timediff(timediff):
    def _format_unit(df, unit):
        return '%d %s%s' % (df, unit, '' if unit == 1 else 's')

    if not timediff:
        return
    timediff = timediff - datetime.datetime.utcnow()
    diff_sec = int(timediff.total_seconds())
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


class StillRunningJob(object):
    """A job that is still running. See the `still_running_template` argument
       to :func:`get_completed_job`."""

    #: The name of the job
    name = None

    #: The password needed to access the job web pages
    passwd = None

    #: Email address used to notify the user of job completion
    email = None

    #: The time (as a datetime.datetime object) when this job was submitted
    submit_time = None

    def __init__(self, name, passwd, email, submit_time):
        self.name, self.passwd, self.email = name, passwd, email
        self.submit_time = submit_time

    def get_refresh_time(self, minseconds):
        """Get a suitable time, in seconds, to wait to refresh the
           'job is still running' page. It will be at least `minseconds`."""
        timediff = datetime.datetime.utcnow() - self.submit_time
        return max(int(timediff.total_seconds()), minseconds)


class CompletedJob(object):
    """A job that has completed. Use :func:`get_completed_job` to create
       such a job from a URL."""

    def __init__(self, sql_dict):
        for k in ('name', 'passwd', 'archive_time', 'directory'):
            setattr(self, k, sql_dict[k])
        self.email = sql_dict['contact_email']
        self._record_results = None

    def get_path(self, fname):
        """Get the full path to a file in the job's directory.

           :param str fname: The file name
           :return: Full path to the file in the job's directory.
        """
        return os.path.join(self.directory, fname)

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

    config = configparser.ConfigParser()

    with open(fname) as fh:
        config.read_file(fh, fname)

    for section in config.sections():
        prefix = '' if section == 'general' else section.upper() + '_'
        for name, value in config.items(section):
            app.config[prefix + name.upper()] = value

    config_dir = os.path.dirname(os.path.abspath(fname))
    frontend_db = config.get('database', 'frontend_config')
    fname = os.path.join(config_dir, frontend_db)
    with open(fname) as fh:
        config.read_file(fh, fname)
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
            fromaddr='no-reply@salilab.org',
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

    #: The login name of the user
    name = None

    #: The first name of the user
    first_name = None

    #: The last name of the user
    last_name = None

    #: The contact email address of the user
    email = None

    #: The user's institution
    institution = None

    #: The user's MODELLER license key
    modeller_key = None

    def __init__(self, name, rd):
        self.name = name
        for k in ('first_name', 'last_name', 'email', 'institution',
                  'modeller_key'):
            setattr(self, k, rd[k])
        # Don't display literal "None" on webpages
        if self.modeller_key is None:
            self.modeller_key = ''


def _get_logged_in_user():
    """Return a LoggedInUser object for the currently logged-in user,
       or None"""
    # Make sure logins are SSL-secured
    if flask.request.scheme != 'https':
        return
    c = _get_servers_cookie_info()
    if (c and 'user_name' in c and 'session' in c
            and c['user_name'] != 'Anonymous'):
        return _get_user_from_cookie(c)


def _get_user_from_cookie(c):
    dbh = get_db()
    cur = MySQLdb.cursors.DictCursor(dbh)
    cur.execute('SELECT first_name,last_name,email,institution,modeller_key '
                'FROM servers.users WHERE user_name=%s '
                'AND password=%s', (c['user_name'], c['session']))
    row = cur.fetchone()
    if row:
        return LoggedInUser(c['user_name'], row)


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


def make_application(name, parameters=[], static_folder='html',
                     *args, **kwargs):
    """Make and return a new Flask application.

       :param str name: Name of the Python file that owns the app. This should
              normally be `__name__`.
       :param list parameters: The form parameters accepted by the 'submit'
              page. This should be a list of :class:`Parameter` and/or
              :class:`FileParameter` objects, and is used to provide help
              for users of the REST API.
       :return: A new Flask application.

       .. note:: Any additional arguments are passed to the Flask constructor.
    """
    # Get environment variable prefix from package name
    env_name = sys.modules[name].__package__.split('.')[0].upper()

    app = flask.Flask(name, *args, static_folder=static_folder, **kwargs)
    _read_config(app, os.environ[env_name + "_CONFIG"])
    app.config['VERSION'] = os.environ[env_name + "_VERSION"]
    app.config['PARAMETERS'] = parameters
    _setup_email_logging(app)
    app.register_blueprint(_blueprint)

    @app.errorhandler(500)
    def handle_internal_error(error):
        ext = 'xml' if _request_wants_xml() else 'html'
        return flask.render_template('saliweb/internal_error.%s' % ext), 500

    @app.errorhandler(_ResultsStillRunningError)
    def handle_results_still_running_error(error):
        if _request_wants_xml():
            template = 'saliweb/results_error.xml'
        else:
            template = error.template or 'saliweb/results_error.html'
        return (flask.render_template(template, message=str(error),
                                      job=error.job), error.http_status)

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

    @app.errorhandler(AccessDeniedError)
    def handle_access_error(error):
        ext = 'xml' if _request_wants_xml() else 'html'
        return (flask.render_template('saliweb/access_denied_error.%s' % ext,
                                      message=str(error)), error.http_status)

    @app.before_request
    def check_login():
        if not hasattr(flask.g, 'user'):
            flask.g.user = _get_logged_in_user()

    @app.teardown_appcontext
    def close_db(error):
        if hasattr(flask.g, 'db_conn'):
            flask.g.db_conn.close()

    @app.teardown_request
    def _cleanup_incoming_jobs(error=None):
        if hasattr(flask.g, 'incoming_jobs'):
            for job in flask.g.incoming_jobs:
                if not job._submitted:
                    shutil.rmtree(job.directory, ignore_errors=True)

    return app


def get_db():
    """Get the MySQL database connection"""
    if not hasattr(flask.g, 'db_conn'):
        app = flask.current_app
        flask.g.db_conn = MySQLdb.connect(
            user=app.config['DATABASE_USER'],
            db=app.config['DATABASE_DB'],
            unix_socket=app.config['DATABASE_SOCKET'],
            passwd=app.config['DATABASE_PASSWD'],
            charset='utf8', use_unicode=True)
    return flask.g.db_conn


def get_completed_job(name, passwd, still_running_template=None):
    """Create and return a new :class:`CompletedJob` for a given URL.
       If the job is not valid (e.g. incorrect password) an exception is
       raised.

       :param str name: The name of the job.
       :param str passwd: Password for the job.
       :param str still_running_template: If given, the name of a Jinja2
              template that will be used to report the 'job is still running'
              error; it is passed the error message as ``message`` and a
              :class:`StillRunningJob` object as ``job``.
       :return: A new CompletedJob.
       :rtype: :class:`CompletedJob`
    """
    def make_ascii(s):
        # name/passwd columns in our DB are latin1, so we will get an
        # "Illegal mix of collations" error if the user passes in random
        # Unicode. Coerce to ASCII to be safe.
        if s is None:
            return s
        return bytes(s, encoding='ascii', errors='replace').decode('ascii')
    conn = get_db()
    c = MySQLdb.cursors.DictCursor(conn)
    c.execute('SELECT * FROM jobs WHERE name=%s AND passwd=%s',
              (make_ascii(name), make_ascii(passwd)))
    job_row = c.fetchone()
    if not job_row:
        raise _ResultsBadJobError('Job does not exist, or wrong password')
    elif job_row['state'] in ('EXPIRED', 'ARCHIVED'):
        raise _ResultsGoneError("Results for job '%s' are no "
                                "longer available for download" % name)
    elif job_row['state'] != 'COMPLETED':
        job = StillRunningJob(name, passwd, job_row['contact_email'],
                              job_row['submit_time'])
        raise _ResultsStillRunningError(
            "Job '%s' has not yet completed; please check back later" % name,
            job, still_running_template)
    return CompletedJob(job_row)


def _request_wants_xml():
    """Return True if the client asked for XML output rather than HTML.
       This is done by adding the HTTP header `Accept: application/xml`
       to the request, and is typically used in the REST API."""
    accept = flask.request.accept_mimetypes
    best = accept.best_match(['application/xml', 'text/html'])
    return best == 'application/xml' and accept[best] > accept['text/html']


def _check_cluster_running(j):
    """Modify job state from RUNNING to QUEUED if it hasn't started yet"""
    if j['state'] == 'RUNNING':
        state_file = os.path.join(j['directory'], 'job-state')
        if not os.path.exists(state_file):
            j['state'] = 'QUEUED'
    return j


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
    running_jobs = [_QueuedJob(_check_cluster_running(x)) for x in c]
    c.execute("SELECT * FROM jobs WHERE state='COMPLETED' "
              "ORDER BY submit_time DESC")
    completed_jobs = [_QueuedJob(x) for x in c]
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


def check_pdb(filename, show_filename=None):
    """Check that a PDB file really looks like a PDB file.
       If it does not, raise an :exc:`InputValidationError` exception.

       :param str filename: The PDB file to check.
       :param str show_filename: If provided, include this filename in any
              error message to identify the PDB file (useful for services
              that allow upload of multiple PDB files).
    """
    if show_filename:
        pdb_file = "PDB file %s" % show_filename
    else:
        pdb_file = "PDB file"
    # Use latin1 to avoid decode errors with 8-bit characters
    with open(filename, encoding='latin1') as fh:
        for line in fh:
            if line.startswith('ATOM  ') or line.startswith('HETATM'):
                return
    raise InputValidationError("%s contains no ATOM or HETATM records!"
                               % pdb_file)


def check_modeller_key(modkey):
    """Check a provided MODELLER key.
       If the key is empty or invalid, raise an
       :exc:`InputValidationError` exception.

       :param str modkey: The MODELLER key to check.
    """
    if not modkey:
        raise InputValidationError("You must enter a valid MODELLER key")
    if modkey != flask.current_app.config['MODELLER_LICENSE_KEY']:
        raise InputValidationError(
            "You have entered an invalid MODELLER key: " + str(modkey))


def _get_pdb_paths(code):
    root = flask.current_app.config['PDB_ROOT']
    code = code.lower()  # PDB codes are case insensitive
    return (os.path.join(root, code[1:3], 'pdb%s.ent.gz' % code),
            'pdb%s.ent' % code)


def pdb_code_exists(code):
    """Return true iff the PDB code (e.g. 1abc) exists in our local
       copy of the PDB."""
    inpdb, outpdb = _get_pdb_paths(code)
    return os.path.exists(inpdb)


def get_pdb_code(code, outdir):
    """Look up the PDB code (e.g. 1abc) in our local copy of the PDB, and
       copy it into the given directory (usually an incoming job directory).
       The file will be named in standard PDB fashion, e.g. ``pdb1abc.ent``.
       The full path to the file is returned. If the code is invalid or
       does not exist, raise an :exc:`InputValidationError` exception.

       :param str code: The PDB code to access (e.g. 1abc)
       :param str outdir: The directory to copy the PDB file into
       :return: The full path to the new file in ``outdir``
    """
    if not re.match('([A-Za-z0-9]+)$', code):
        raise InputValidationError(
            "You have entered an invalid PDB code; valid codes "
            "contain only letters and numbers, e.g. 1abc")
    in_pdb, out_pdb = _get_pdb_paths(code)
    if not os.path.exists(in_pdb):
        raise InputValidationError(
            "PDB code '%s' does not exist in our copy of the PDB database."
            % code)
    out_pdb = os.path.join(outdir, out_pdb)
    with gzip.open(in_pdb, 'rb') as fh_in, open(out_pdb, 'wb') as fh_out:
        shutil.copyfileobj(fh_in, fh_out)
    return out_pdb


def _get_chains_in_pdb(pdb_file):
    """Get a set of all chains in the given PDB file"""
    def yield_chains(fh):
        for line in fh:
            if line.startswith('HETATM') or line.startswith('ATOM'):
                yield line[21]
    with open(pdb_file) as fh:
        return frozenset(chain for chain in yield_chains(fh) if chain != ' ')


def _filter_pdb_chains(in_pdb, out_pdb, chain_ids):
    """Make a new PDB file containing only the given chains from the input"""
    with open(in_pdb) as fh_in:
        with open(out_pdb, 'w') as fh_out:
            for line in fh_in:
                if ((line.startswith('ATOM') or line.startswith('HETATM'))
                        and line[21] in chain_ids):
                    fh_out.write(line)


def get_pdb_chains(pdb_chain, outdir):
    """Similar to :func:`get_pdb_code`, find a PDB in our database, and make a
       new PDB containing just the requested one-letter chains (if any)
       in the given directory. The PDB code and the chains are separated
       by a colon. (If there is no colon, no chains, or the chains are
       just '-', this does the same thing as :func:`get_pdb_code`.)
       For example, '1xyz:AC' would make a new PDB file containing just
       the A and C chains from the 1xyz PDB. The full path to the file
       is returned. If the code is invalid or does not exist, or at least
       one chain is specified that is not in the PDB file, raise
       an :exc:`InputValidationError` exception.

       :param str pdb_chain: PDB code and chain IDs, separated by a colon
       :param str outdir: Directory to write the PDB file into
       :return: Full path to the new PDB file
    """

    pdb_split = pdb_chain.split(':')

    pdb_file = get_pdb_code(pdb_split[0], outdir)
    if len(pdb_split) == 1 or pdb_split[1] == '-':  # no chains given
        return pdb_file

    chain_ids = pdb_split[1].upper()
    if not re.match(r'\w*$', chain_ids):
        raise InputValidationError("Invalid chain IDs %s", chain_ids)

    # Check user-specified chains exist in PDB
    pdb_chains = _get_chains_in_pdb(pdb_file)
    missing = ", ".join(c for c in chain_ids if c not in pdb_chains)
    if missing:
        missing_txt = " %s does" if len(missing) == 1 else "s %s do"
        raise InputValidationError(
            "The given chain%s not exist in the PDB file" %
            (missing_txt % chain_ids))

    out_pdb_file = os.path.join(outdir, "%s%s.pdb" % (pdb_split[0], chain_ids))
    _filter_pdb_chains(pdb_file, out_pdb_file, frozenset(chain_ids))
    os.unlink(pdb_file)
    return out_pdb_file


def render_results_template(template_name, job, extra_xml_outputs=[],
                            extra_xml_metadata={}, extra_xml_links={},
                            **context):
    """Render a template for the job results page.
       This normally functions like `flask.render_template` but will instead
       return XML if the user requests it (for the REST API). The XML file
       will include download links to any file mentioned in the template
       with :meth:`CompletedJob.get_results_file_url`. Extra downloadable files
       can be added to the XML output by listing them in `extra_xml_outputs`.
       Custom tags can also be added to the XML output by listing them in
       `extra_xml_metadata`, which is a dict (keys are XML tag names, values
       are the XML values). `extra_xml_links` is similar except that the values
       are hyperlinks (xlink:href targets).
    """
    if _request_wants_xml():
        job._record_results = []
    r = flask.render_template(template_name, job=job, **context)
    if job._record_results is not None:
        for o in extra_xml_outputs:
            job.get_results_file_url(o)
        return flask.render_template('saliweb/results.xml',
                                     results=job._record_results,
                                     extra_xml_metadata=extra_xml_metadata,
                                     extra_xml_links=extra_xml_links)
    else:
        return r


def render_submit_template(template_name, job, **context):
    """Render a template for the job submission page.
       This normally functions like `flask.render_template` but will instead
       return XML if the user requests it (for the REST API).

       For very quick jobs that take only a few seconds to run, consider using
       :func:`redirect_to_results_page` instead.
    """
    if _request_wants_xml():
        return flask.render_template('saliweb/submit.xml', job=job)
    else:
        return flask.render_template(template_name, job=job, **context)


def redirect_to_results_page(job):
    """Perform a redirect from the job-submission page to the job-results page.
       This normally functions like `flask.redirect`, but will instead return
       an XML document if the user requests it (for the REST API).

       This can be used instead of :func:`render_submit_template` for a
       just-submitted job. (This is more appropriate for jobs that take only
       a few seconds to run.) The job results page should in turn call
       :func:`get_completed_job` with the ``still_running_template``
       parameter to provide information on the job submission.

       :param job: The just-submitted job.
       :type job: :class:`IncomingJob`
    """
    if _request_wants_xml():
        return flask.render_template('saliweb/submit.xml', job=job)
    else:
        return flask.redirect(url_for("results", name=job.name,
                                      passwd=job._passwd))
