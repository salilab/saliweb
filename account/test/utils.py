import flask
import sys
import os
import md5


# Make reading flask config a noop
def _mock_from_pyfile(self, fname, silent=False):
    pass
flask.Config.from_pyfile = _mock_from_pyfile


def _set_search_paths(fname):
    """Set search paths so that we can import Python modules and use mocks"""
    # Path to mocks
    sys.path.insert(0, os.path.join(os.path.dirname(fname), 'mock'))
    # Path to top level
    sys.path.insert(0, os.path.join(os.path.dirname(fname), '..'))


def import_mocked_account(fname):
    """Import the 'account' module, mocked to make testing easier"""
    _set_search_paths(fname)
    account = __import__("account")
    account.app.testing = True
    account.app.config['DATABASE_USER'] = 'testuser'
    account.app.config['DATABASE_SOCKET'] = '/not/exist'
    account.app.config['DATABASE_PASSWD'] = 'testpwd'
    account.app.config['SECRET_KEY'] = 'test-secret-key'
    return account


def set_logged_in_user(username):
    import saliweb.frontend
    if username is None:
        flask.g.user = None
    else:
        rd = {'email': 'testemail', 'first_name': 'foo', 'last_name': 'bar',
              'institution': 'testin'}
        flask.g.user = saliweb.frontend.LoggedInUser(username, rd)


def set_servers_cookie(client, user, passwd):
    hashpw = md5.md5(passwd).hexdigest()
    client.set_cookie('localhost', 'sali-servers',
                      'user_name&%s&session&%s' % (user, hashpw))
