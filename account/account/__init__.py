from flask import (Flask, g, render_template, request, redirect, url_for,
                   flash, after_this_request, abort)
import MySQLdb.cursors
import logging.handlers
import saliweb.frontend
import datetime
import string
import random
import smtplib
import email.mime.text


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
    error = check_password(f['password'], f['passwordcheck'])
    if error:
        return error
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
    update_login_cookie(cur, f['user_name'], f.get('permanent'))


@app.route('/logout')
def logout():
    flash("You have been logged out.")
    set_servers_cookie_info({'user_name': 'Anonymous', 'session': ''}, False)
    return redirect(url_for("index"))


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    # User needs to be logged in
    if not g.user:
        abort(403)
    error = None
    if request.method == 'GET':
        # Populate form variables from logged-in user
        form = g.user
    else:
        # Form variables from last cycle
        form = request.form
        if not all((form['first_name'], form['last_name'],
                    form['institution'], form['email'])):
            error = "Please fill out all form fields."
        else:
            dbh = saliweb.frontend.get_db()
            cur = dbh.cursor()
            cur.execute('UPDATE servers.users SET first_name=%s,last_name=%s,'
                        'email=%s,institution=%s WHERE user_name=%s',
                        (form['first_name'], form['last_name'], form['email'],
                         form['institution'], g.user.name))
            flash("Profile updated.")
            return redirect(url_for('index'))
    return render_template('profile.html', error=error, form=form)


@app.route('/password', methods=['GET', 'POST'])
def password():
    # User needs to be logged in
    if not g.user:
        abort(403)
    error = None
    if request.method == 'POST':
        error = change_password()
        if not error:
            flash("Password changed successfully.")
            return redirect(url_for('index'))
    return render_template('password.html', error=error)


def change_password():
    """Change password of logged-in user"""
    f = request.form
    dbh = saliweb.frontend.get_db()
    cur = dbh.cursor()
    cur.execute('SELECT user_name FROM servers.users WHERE user_name=%s '
                'AND password=PASSWORD(%s)', (g.user.name, f['oldpassword']))
    if not cur.fetchone():
        return "Incorrect old password entered."
    error = check_password(f['newpassword'], f['passwordcheck'])
    if error:
        return error
    cur.execute('UPDATE servers.users SET password=PASSWORD(%s) '
                'WHERE user_name=%s', (f['newpassword'], g.user.name))
    # todo: inherit age from previous login cookie
    update_login_cookie(cur, g.user.name, permanent=True)


def update_login_cookie(cur, user_name, permanent):
    # Get password hash to set the login cookie
    cur.execute('SELECT password FROM servers.users WHERE user_name=%s',
                (user_name,))
    cookie = {'user_name': user_name, 'session': cur.fetchone()[0]}
    set_servers_cookie_info(cookie, permanent)


def check_password(password, passwordcheck):
    """Do basic sanity checks on a password entered in a form"""
    if len(password) < 8:
        return "Passwords should be at least 8 characters long."
    if password != passwordcheck:
        return "Password check failed. The two passwords are not identical."


@app.route('/reset', methods=['GET', 'POST'])
def reset():
    error = None
    if request.method == 'POST':
        email = request.form['email']
        error = send_reset_email(email)
        if not error:
            return render_template("reset-sent.html", email=email)
    return render_template('reset.html', error=error)


@app.route('/reset/<int:user_id>/<reset_key>', methods=['GET', 'POST'])
def reset_link(user_id, reset_key):
    error = None
    dbh = saliweb.frontend.get_db()
    cur = dbh.cursor()
    cur.execute('SELECT user_name FROM servers.users WHERE user_id=%s '
                'AND reset_key IS NOT NULL AND reset_key=%s AND '
                'reset_key_expires > %s',
                (user_id, reset_key, datetime.datetime.now()))
    row = cur.fetchone()
    if not row:
        return render_template("reset-link-error.html")
    user_name = row[0]

    if request.method == 'POST':
        f = request.form
        error = check_password(f['password'], f['passwordcheck'])
        if not error:
            cur.execute('UPDATE servers.users SET password=PASSWORD(%s) '
                        'WHERE user_name=%s', (f['password'], user_name))
            update_login_cookie(cur, user_name, request.form.get('permanent'))
            cur.execute('UPDATE servers.users SET reset_key=NULL '
                        'WHERE user_id=%s', (user_id,))
            flash("Password reset successfully. You are now logged in.")
            return redirect(url_for('index'))
    else:
        permanent = True
    return render_template('reset-link.html', error=error, user_name=user_name,
                           permanent=True)


def send_reset_email(email):
    dbh = saliweb.frontend.get_db()
    cur = dbh.cursor()
    cur.execute('SELECT user_id FROM servers.users WHERE email=%s', (email,))
    row = cur.fetchone()
    if not row:
        return "No account found with email %s" % email
    user_id = row[0]
    reset_key = _generate_random_password(30)
    expires = datetime.datetime.now() + datetime.timedelta(days=2)
    cur.execute('UPDATE servers.users SET reset_key=%s, reset_key_expires=%s '
                ' WHERE user_id=%s', (reset_key, expires, user_id))
    s = smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT'])
    mail_from = app.config['MAIL_FROM']
    msg = get_reset_email_body(user_id, reset_key)
    msg['From'] = mail_from
    msg['To'] = email
    s.sendmail(mail_from, email, msg.as_string())
    s.quit()


def get_reset_email_body(user_id, reset_key):
    body = """
Please use the link below to reset your password for Sali Lab web
services at https://salilab.org/.

This is a temporary link, and will expire in 2 days.

Reset link:
%s

If you did not request this password reset, feel free to ignore this email.
""" % url_for("reset_link", user_id=user_id,
              reset_key=reset_key, _external=True)
    msg = email.mime.text.MIMEText(body)
    msg['Subject'] = 'Password reset for Sali Lab web services'
    return msg


def _generate_random_password(length):
    """Generate a random alphanumeric password of the given length"""
    valid = string.ascii_lowercase + string.ascii_uppercase + string.digits
    return ''.join(random.choice(valid) for _ in range(length))
