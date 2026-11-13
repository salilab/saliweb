import flask
import sys
import os
import hashlib
import contextlib
import re


# Make reading flask config a noop
def _mock_from_pyfile(self, fname, silent=False):
    pass


flask.Config.from_pyfile = _mock_from_pyfile


def _set_search_paths(fname):
    """Set search paths so that we can import Python modules and use mocks"""
    # Path to mocks
    sys.path.insert(0, os.path.join(os.path.dirname(fname), 'mock'))
    # Path to top level for 'account'
    sys.path.insert(0, os.path.join(os.path.dirname(fname), '..'))
    # Path to top level for 'saliweb.frontend'
    sys.path.insert(0, os.path.join(os.path.dirname(fname), '..', '..',
                                    'python'))


def import_mocked_account(fname):
    """Import the 'account' module, mocked to make testing easier"""
    _set_search_paths(fname)
    account = __import__("account")
    account.app.testing = True
    account.app.config['DATABASE_USER'] = 'testuser'
    account.app.config['DATABASE_SOCKET'] = '/not/exist'
    account.app.config['DATABASE_PASSWD'] = 'testpwd'
    account.app.config['SECRET_KEY'] = 'test-secret-key'
    # Most tests don't need CSRF tokens; see csrf_enabled() for those that do
    account.app.config['WTF_CSRF_ENABLED'] = False
    account.app.config['MAIL_SERVER'] = 'localhost'
    account.app.config['MAIL_PORT'] = 25
    account.app.config['MAIL_FROM'] = 'noreply@localhost'
    return account


def set_logged_in_user(username):
    import saliweb.frontend
    if username is None:
        flask.g.user = None
    else:
        rd = {'email': 'testemail', 'first_name': 'foo', 'last_name': 'bar',
              'institution': 'testin', 'modeller_key': 'modkey'}
        flask.g.user = saliweb.frontend.LoggedInUser(username, rd)


def set_servers_cookie(client, user, passwd):
    passwd = passwd.encode('utf-8')
    hashpw = hashlib.md5(passwd).hexdigest()
    try:
        client.set_cookie(key='sali-servers',
                          value='user_name&%s&session&%s' % (user, hashpw))
    except TypeError:  # werkzeug 2
        client.set_cookie(key='sali-servers',
                          value='user_name&%s&session&%s' % (user, hashpw),
                          server_name='localhost')


@contextlib.contextmanager
def csrf_enabled(app):
    """Turn on CSRF protection for the duration of the context"""
    app.config['WTF_CSRF_ENABLED'] = True
    try:
        yield
    finally:
        app.config['WTF_CSRF_ENABLED'] = False


def get_csrf_token(client, url):
    """Get the CSRF token from the form on the given page"""
    rv = client.get(url, base_url='https://localhost')
    m = re.search(rb'name="csrf_token" value="([^"]+)"', rv.data)
    return m.group(1).decode('ascii')
