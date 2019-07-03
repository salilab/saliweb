import flask
from flask import url_for, Markup
import datetime
import ConfigParser
import os
import logging.handlers
import MySQLdb


class ResultsError(Exception):
    pass


class ResultsBadJobError(ResultsError):
    http_status = 400


class ResultsGoneError(ResultsError):
    http_status = 410


class ResultsStillRunningError(ResultsError):
    http_status = 503


def _format_timediff(timediff):
    def _format_unit(df, unit):
        return '%d %s%s' % (df, unit, '' if unit == 1 else 's')

    if not timediff:
        return
    timediff = (timediff - datetime.datetime.utcnow()).total_seconds()
    if timediff < 0:
        return
    if timediff < 120:
        return _format_unit(timediff, 'second')
    timediff /= 60.0
    if timediff < 120:
        return _format_unit(timediff, 'minute')
    timediff /= 60.0
    if timediff < 48:
        return _format_unit(timediff, 'hour')
    timediff /= 24.0
    if timediff < 48:
        return _format_unit(timediff, 'day')


class QueuedJob(object):
    def __init__(self, sql_dict):
        for k in ('name', 'submit_time', 'state'):
            setattr(self, k, sql_dict[k])


class CompletedJob(object):

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


blueprint = flask.Blueprint('saliweb', __name__, template_folder='templates')


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


def make_application(name, config, *args, **kwargs):
    """Make and return a Flask application.
       `name` should normally be `__name__`; `config` is the path to the
       web service config file. Other arguments are passed to the Flask
       constructor."""
    app = flask.Flask(name, *args, **kwargs)
    _read_config(app, config)
    _setup_email_logging(app)
    app.register_blueprint(blueprint)

    @app.errorhandler(ResultsError)
    def handle_custom_error(error):
        return (flask.render_template('saliweb/error.html', message=str(error)),
                error.http_status)

    @app.route('/queue')
    def queue():
        conn = get_db()
        c = MySQLdb.cursors.DictCursor(conn)
        c.execute("SELECT * FROM jobs WHERE state != 'ARCHIVED' AND state != 'EXPIRED' AND state != 'COMPLETED' ORDER BY submit_time DESC")
        running_jobs = [ QueuedJob(x) for x in c ]
        c.execute("SELECT * FROM jobs WHERE state='COMPLETED' ORDER BY submit_time DESC")
        completed_jobs = [ QueuedJob(x) for x in c ]
        return flask.render_template('saliweb/queue.html', running_jobs=running_jobs, completed_jobs=completed_jobs)

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
    conn = get_db()
    c = MySQLdb.cursors.DictCursor(conn)
    c.execute('SELECT * FROM jobs WHERE name=%s AND passwd=%s', (name, passwd))
    job_row = c.fetchone()
    if not job_row:
        raise ResultsBadJobError('Job does not exist, or wrong password')
    else:
        if job_row['state'] in ('EXPIRED', 'ARCHIVED'):
            raise ResultsGoneError("Results for job '%s' are no longer available for download" % name)
        else:
            if job_row['state'] != 'COMPLETED':
                raise ResultsStillRunningError("Job '%s' has not yet completed; please check back later" % name)
    return CompletedJob(job_row)
