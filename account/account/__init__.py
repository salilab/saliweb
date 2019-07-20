from flask import (Flask, g, render_template, request, redirect, url_for,
                   flash, after_this_request)
import MySQLdb.cursors
import logging.handlers
import saliweb.frontend
import datetime


def setup_logging(app):
    if not app.debug and 'MAIL_SERVER' in app.config:
        mail_handler = logging.handlers.SMTPHandler(
            mailhost=(app.config['MAIL_SERVER'], app.config['MAIL_PORT']),
            fromaddr=app.config['MAIL_FROM'],
            toaddrs=app.config['MAIL_TO'],
            subject='Web server account page error')
        mail_handler.setLevel(logging.ERROR)
        app.logger.addHandler(mail_handler)


app = Flask(__name__, instance_relative_config=True)
app.config['DATABASE_DB'] = 'servers'
app.config.from_pyfile('account.cfg')
setup_logging(app)
app.register_blueprint(saliweb.frontend._blueprint)


@app.before_request
def check_login():
    g.user = saliweb.frontend._get_logged_in_user()


@app.teardown_appcontext
def close_db(error):
    if hasattr(g, 'db_conn'):
        g.db_conn.close()


@app.route('/', methods=['GET', 'POST'])
def index():
    error = None
    if request.method == 'POST':
        user = request.form['user_name']
        passwd = request.form['password']
        dbh = saliweb.frontend.get_db()
        cur = dbh.cursor()
        cur.execute('SELECT password FROM servers.users WHERE user_name=%s '
                    'AND password=PASSWORD(%s)', (user, passwd))
        row = cur.fetchone()
        if row:
            pwhash = row[0]
            cookie = {'user_name': user, 'session': row[0]}
            set_servers_cookie_info(cookie, request.form.get('permanent'))
            g.user = saliweb.frontend._get_user_from_cookie(cookie)
            if not g.user:
                raise RuntimeError("Could not look up user info")
        else:
            error = "Invalid username or password"
    if g.user:
        return render_template('logged_in.html', servers=get_servers())
    else:
        return render_template('logged_out.html', error=error)


def get_servers():
    """Get all servers that the current user can access"""
    dbh = saliweb.frontend.get_db()
    cur = MySQLdb.cursors.DictCursor(dbh)
    cur.execute("SELECT server FROM access WHERE user_name=%s "
                "OR user_name='Anonymous'", (g.user.name,))
    available = frozenset(row['server'] for row in cur)

    cur.execute("SELECT server,url,title,short_title FROM servers "
                "ORDER BY short_title")
    return [row for row in cur if row['server'] in available]


def set_servers_cookie_info(cookie, permanent):
    if permanent:
        delta = datetime.timedelta(days=365)
        expires = datetime.datetime.now() + delta
        try:
            age = int(delta.total_seconds())
        except AttributeError:  # python 2.6
            age = int(delta.days * 24 * 60 * 60 + delta.seconds)
    else:
        age = expires = None
    user = cookie['user_name']
    pwhash = cookie['session']

    @after_this_request
    def add_cookie(response):
        response.set_cookie(key='sali-servers',
                            value='user_name&%s&session&%s' % (user, pwhash),
                            secure=True, max_age=age, expires=expires)
        return response


@app.route('/help')
def help():
    return render_template('help.html')


@app.route('/contact')
def contact():
    return render_template('contact.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        error = create_account()
        if not error:
            flash("Account successfully created.")
            return redirect(url_for('index'))
    return render_template('register.html', error=error, form=request.form)


def create_account():
    """Create a new account using form parameters"""
    f = request.form
    if not f.get('academic'):
        return "The Sali Lab servers are only open for the academic community."
    if len(f['password']) < 8:
        return "Passwords should be at least 8 characters long."
    if f['password'] != f['passwordcheck']:
        return "Password check failed. The two passwords are not identical."
    if not all((f['user_name'], f['first_name'], f['last_name'],
                f['institution'], f['email'])):
        return "Please fill out all form fields."
    dbh = saliweb.frontend.get_db()
    cur = dbh.cursor()
    cur.execute('SELECT user_name FROM servers.users WHERE user_name=%s',
                (f['user_name'],))
    if cur.fetchone():
        return ("User name %s already exists. Please choose a "
                "different one." % f['user_name'])
    cur.execute('INSERT INTO servers.users (user_name,password,ip_addr,'
                'first_name,last_name,email,institution,date_added) VALUES '
                '(%s, PASSWORD(%s), %s, %s, %s, %s, %s, %s)',
                (f['user_name'], f['password'], request.remote_addr,
                 f['first_name'], f['last_name'], f['email'],
                 f['institution'], datetime.datetime.now()))
    # Get password hash to set the login cookie
    cur.execute('SELECT password FROM servers.users WHERE user_name=%s',
                (f['user_name'],))
    cookie = {'user_name': f['user_name'], 'session': cur.fetchone()[0]}
    set_servers_cookie_info(cookie, f.get('permanent'))


@app.route('/logout')
def logout():
    flash("You have been logged out.")
    set_servers_cookie_info({'user_name': 'Anonymous', 'session': ''}, False)
    return redirect(url_for("index"))