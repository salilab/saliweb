from flask import (Flask, g, render_template, request, redirect, url_for,
                   flash, abort)
import saliweb.frontend
import datetime
from . import util


app = Flask(__name__, instance_relative_config=True)
app.config['DATABASE_DB'] = 'servers'
app.config.from_pyfile('account.cfg')
util.setup_logging(app)
app.register_blueprint(saliweb.frontend._blueprint)


@app.errorhandler(500)
def handle_internal_error(error):
    return render_template('saliweb/internal_error.html'), 500


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
            util.set_servers_cookie_info(cookie, request.form.get('permanent'))
            g.user = saliweb.frontend._get_user_from_cookie(cookie)
            if not g.user:
                raise RuntimeError("Could not look up user info")
        else:
            error = "Invalid username or password"
    if g.user:
        return render_template('logged_in.html', servers=util.get_servers())
    else:
        return render_template('logged_out.html', error=error)


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
        error = util.create_account()
        if not error:
            flash("Account successfully created.")
            return redirect(url_for('index'))
    return render_template('register.html', error=error, form=request.form)


@app.route('/logout')
def logout():
    flash("You have been logged out.")
    util.set_servers_cookie_info({'user_name': 'Anonymous', 'session': ''},
                                 False)
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
            error = "Please fill out all required form fields."
        else:
            dbh = saliweb.frontend.get_db()
            cur = dbh.cursor()
            cur.execute('UPDATE servers.users SET first_name=%s,last_name=%s,'
                        'email=%s,institution=%s,modeller_key=%s WHERE '
                        'user_name=%s',
                        (form['first_name'], form['last_name'], form['email'],
                         form['institution'], form['modeller_key'],
                         g.user.name))
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
        error = util.change_password()
        if not error:
            flash("Password changed successfully.")
            return redirect(url_for('index'))
    return render_template('password.html', error=error)


@app.route('/reset', methods=['GET', 'POST'])
def reset():
    error = None
    if request.method == 'POST':
        email = request.form['email']
        error = util.send_reset_email(email, app)
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
        error = util.check_password(f['password'], f['passwordcheck'])
        if not error:
            cur.execute('UPDATE servers.users SET password=PASSWORD(%s), '
                        'reset_key=NULL WHERE user_name=%s',
                        (f['password'], user_name))
            util.update_login_cookie(cur, user_name,
                                     request.form.get('permanent'))
            flash("Password reset successfully. You are now logged in.")
            return redirect(url_for('index'))
    else:
        permanent = True
    return render_template('reset-link.html', error=error, user_name=user_name,
                           permanent=True)
