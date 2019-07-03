from flask import Blueprint, url_for, Markup, Flask
import datetime
import ConfigParser
import os
import logging.handlers


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


blueprint = Blueprint('saliweb', __name__, template_folder='templates')


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
    app = Flask(name, *args, **kwargs)
    _read_config(app, config)
    _setup_email_logging(app)
    app.register_blueprint(blueprint)
    return app
