from flask import after_this_request, request, url_for, g
import logging.handlers
import saliweb.frontend
import MySQLdb.cursors
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
        age = int(delta.total_seconds())
    else:
        age = expires = None
    user = cookie['user_name']
    pwhash = cookie['session']

    @after_this_request
    def add_cookie(response):
        response.set_cookie(key='sali-servers',
                            value='user_name&%s&session&%s' % (user, pwhash),
                            secure=True, httponly=True, max_age=age,
                            expires=expires, samesite='Lax')
        return response


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
        return "Please fill out all required form fields."
    elif (len(f['user_name']) > 25 or
          any((f[x] and len(f[x]) > 40)
              for x in ('first_name', 'last_name', 'institution',
                        'email', 'modeller_key'))):
        return "Form field too long."
    dbh = saliweb.frontend.get_db()
    cur = dbh.cursor()
    cur.execute('SELECT user_name FROM servers.users WHERE user_name=%s',
                (f['user_name'],))
    if cur.fetchone():
        return ("User name %s already exists. Please choose a "
                "different one." % f['user_name'])
    cur.execute('INSERT INTO servers.users (user_name,password,ip_addr,'
                'first_name,last_name,email,institution,modeller_key,'
                'date_added) VALUES '
                '(%s, PASSWORD(%s), %s, %s, %s, %s, %s, %s, %s)',
                (f['user_name'], f['password'], request.remote_addr,
                 f['first_name'], f['last_name'], f['email'],
                 f['institution'], f['modeller_key'], datetime.datetime.now()))
    update_login_cookie(cur, f['user_name'], f.get('permanent'))


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
    update_login_cookie(cur, g.user.name, f.get('permanent'))


def update_login_cookie(cur, user_name, permanent):
    # Get password hash to set the login cookie
    cur.execute('SELECT password FROM servers.users WHERE user_name=%s',
                (user_name,))
    cookie = {'user_name': user_name, 'session': cur.fetchone()[0]}
    set_servers_cookie_info(cookie, permanent)


def check_password(password, passwordcheck):
    """Do basic sanity checks on a password entered in a form"""
    if len(password) < 8 or len(password) > 25:
        return "Passwords should be between 8 and 25 characters long."
    if password != passwordcheck:
        return "Password check failed. The two passwords are not identical."


def send_reset_email(email, app):
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
    try:
        s.sendmail(mail_from, email, msg.as_string())
    except smtplib.SMTPRecipientsRefused:
        return ("Failed to send a password reset email. This may be because "
                "your account's email address is invalid. Please contact us "
                "so we can reset your password for you.")
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
