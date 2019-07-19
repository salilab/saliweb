import utils
import re
import flask
account = utils.import_mocked_account(__file__)


def test_logged_out_index():
    """Test logged-out index page"""
    c = account.app.test_client()
    rv = c.get('/')
    r = re.compile('Sali Lab Web Server Login.*Username:.*Password.*'
                   'log on permanently', re.DOTALL | re.MULTILINE)
    assert r.search(rv.data)


def test_logged_in_index():
    """Test logged-in index page"""
    c = account.app.test_client()
    utils.set_servers_cookie(c, 'authuser', 'authpw')
    rv = c.get('/', base_url='https://localhost')  # force HTTPS
    r = re.compile('Server availability for user authuser.*'
                   'short1, long title1.*'
                   'short2, long title2.*'
                   'Profile.*'
                   'Login:.*authuser.*', re.DOTALL | re.MULTILINE)
    assert r.search(rv.data)


def test_bad_log_in():
    """Test failure to log in"""
    c = account.app.test_client()
    rv = c.post('/', data={'user_name': 'baduser', 'password': 'badpasswd'})
    r = re.compile('Error:.*Invalid username or password.*'
                   'Sali Lab Web Server Login',
                   re.DOTALL | re.MULTILINE)
    assert r.search(rv.data)


def test_good_log_in_temporary():
    """Test successful log in with temporary cookie"""
    c = account.app.test_client()
    rv = c.post('/', data={'user_name': 'authuser', 'password': 'authpw'})
    r = re.compile('Server availability for user authuser.*'
                   'short1, long title1.*'
                   'short2, long title2.*'
                   'Profile.*'
                   'Login:.*authuser.*', re.DOTALL | re.MULTILINE)
    assert r.search(rv.data)
    assert (rv.headers['Set-Cookie'] ==
            'sali-servers=user_name&authuser&session&'
            '46650befec4c54b4443d4b8a1ad5135a; Secure; Path=/')


def test_good_log_in_permanent():
    """Test successful log in with permanent cookie"""
    c = account.app.test_client()
    rv = c.post('/', data={'user_name': 'authuser', 'password': 'authpw',
                           'permanent': 'on'})
    r = re.compile('Server availability for user authuser.*'
                   'short1, long title1.*'
                   'short2, long title2.*'
                   'Profile.*'
                   'Login:.*authuser.*', re.DOTALL | re.MULTILINE)
    assert r.search(rv.data)
    assert 'Expires=' in rv.headers['Set-Cookie']
    assert 'Max-Age=31536000' in rv.headers['Set-Cookie']


def test_get_servers():
    """Test get_servers()"""
    with account.app.app_context():
        # Authorized user can see both public and private servers
        utils.set_logged_in_user('authuser')
        servers = account.get_servers()
        assert [s['server'] for s in servers] == ['public', 'private']

        # Unauthorized user can only see public servers
        utils.set_logged_in_user('unauthuser')
        servers = account.get_servers()
        assert [s['server'] for s in servers] == ['public']


def test_help():
    """Test help page"""
    c = account.app.test_client()
    rv = c.get('/help')
    r = re.compile('Account Information.*Access Control',
                   re.DOTALL | re.MULTILINE)
    assert r.search(rv.data)


def test_contact():
    """Test contact page"""
    c = account.app.test_client()
    rv = c.get('/contact')
    r = re.compile('Contact.*modbase.*salilab\.org',
                   re.DOTALL | re.MULTILINE)
    assert r.search(rv.data)


def test_register():
    """Test register page"""
    c = account.app.test_client()
    rv = c.get('/register')
    r = re.compile('Create an Account.*log on permanently',
                   re.DOTALL | re.MULTILINE)
    assert r.search(rv.data)


def test_logout():
    """Test logout page"""
    c = account.app.test_client()
    rv = c.get('/logout')
    assert rv.status_code == 302  # redirect to index page


def test_setup_logging():
    """Test setup_logging()"""
    class MockLogger(object):
        def addHandler(self, h):
            self.h = h

    class MockApp(object):
        def __init__(self):
            self.debug = False
            self.config = {'MAIL_SERVER': 'localhost', 'MAIL_PORT': 25,
                           'MAIL_FROM': 'noreply@localhost',
                           'MAIL_TO': 'test@localhost'}
            self.logger = MockLogger()
    mock_app = MockApp()
    account.setup_logging(mock_app)
    assert mock_app.logger.h is not None
