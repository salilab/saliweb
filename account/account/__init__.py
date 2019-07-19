from flask import Flask, g, render_template, request, redirect, url_for, flash
import logging.handlers
import saliweb.frontend
import datetime


app = Flask(__name__, instance_relative_config=True)
app.config['DATABASE_DB'] = 'servers'
app.config.from_pyfile('account.cfg')

if not app.debug and 'MAIL_SERVER' in app.config:
    mail_handler = logging.handlers.SMTPHandler(
        mailhost=(app.config['MAIL_SERVER'], app.config['MAIL_PORT']),
        fromaddr=app.config['MAIL_FROM'],
        toaddrs=app.config['MAIL_TO'], subject='Web server account page error')
    mail_handler.setLevel(logging.ERROR)
    app.logger.addHandler(mail_handler)

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
    cookie = None
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
            resp = redirect(url_for("profile"))
            if request.form.get('permanent'):
                age = datetime.timedelta(days=365)
                expires = datetime.datetime.now() + age
                age = age.total_seconds()
            else:
                age = expires = None
            resp.set_cookie(key='sali-servers',
                            value='user_name&%s&session&%s' % (user, pwhash),
                            secure=True, max_age=age, expires=expires)
            return resp
        else:
            error = "Invalid username or password"
    elif g.user:
        return redirect(url_for("profile"))
    return render_template('index.html', error=error)


@app.route('/profile')
def profile():
    return render_template('profile.html')


@app.route('/help')
def help():
    return render_template('help.html')


@app.route('/contact')
def contact():
    return render_template('contact.html')


@app.route('/register')
def register():
    return render_template('register.html')


@app.route('/logout')
def logout():
    flash("You have been logged out.")
    resp = redirect(url_for("index"))
    resp.set_cookie(key='sali-servers', value='user_name&Anonymous&session&',
                    secure=True, max_age=None)
    return resp
