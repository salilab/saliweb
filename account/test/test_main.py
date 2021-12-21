import utils
import re
account = utils.import_mocked_account(__file__)


def test_logged_out_index():
    """Test logged-out index page"""
    c = account.app.test_client()
    rv = c.get('/')
    r = re.compile(b'Sali Lab Web Server Login.*Username:.*Password.*'
                   b'log on permanently', re.DOTALL | re.MULTILINE)
    assert r.search(rv.data)


def test_logged_in_index():
    """Test logged-in index page"""
    c = account.app.test_client()
    utils.set_servers_cookie(c, 'authuser', 'authpw00')
    rv = c.get('/', base_url='https://localhost')  # force HTTPS
    r = re.compile(b'Server availability for user authuser.*'
                   b'short1, long title1.*'
                   b'short2, long title2.*'
                   b'Profile.*'
                   b'Login:.*authuser.*', re.DOTALL | re.MULTILINE)
    assert r.search(rv.data)


def test_bad_log_in():
    """Test failure to log in"""
    c = account.app.test_client()
    rv = c.post('/', data={'user_name': 'baduser', 'password': 'badpasswd'})
    r = re.compile(b'Error:.*Invalid username or password.*'
                   b'Sali Lab Web Server Login',
                   re.DOTALL | re.MULTILINE)
    assert r.search(rv.data)


def test_good_log_in_temporary():
    """Test successful log in with temporary cookie"""
    c = account.app.test_client()
    rv = c.post('/', data={'user_name': 'authuser', 'password': 'authpw00'})
    r = re.compile(b'Server availability for user authuser.*'
                   b'short1, long title1.*'
                   b'short2, long title2.*'
                   b'Profile.*'
                   b'Login:.*authuser.*', re.DOTALL | re.MULTILINE)
    assert r.search(rv.data)
    assert (rv.headers['Set-Cookie'] ==
            'sali-servers=user_name&authuser&session&'
            'bce42b481e4c5f9012ad7da17c7c141b; Secure; HttpOnly; Path=/; '
            'SameSite=Lax')


def test_good_log_in_permanent():
    """Test successful log in with permanent cookie"""
    c = account.app.test_client()
    rv = c.post('/', data={'user_name': 'authuser', 'password': 'authpw00',
                           'permanent': 'on'})
    r = re.compile(b'Server availability for user authuser.*'
                   b'short1, long title1.*'
                   b'short2, long title2.*'
                   b'Profile.*'
                   b'Login:.*authuser.*', re.DOTALL | re.MULTILINE)
    assert r.search(rv.data)
    assert 'Expires=' in rv.headers['Set-Cookie']
    assert 'Max-Age=31536000' in rv.headers['Set-Cookie']


def test_get_servers():
    """Test get_servers()"""
    with account.app.app_context():
        # Authorized user can see both public and private servers
        utils.set_logged_in_user('authuser')
        servers = account.util.get_servers()
        assert [s['server'] for s in servers] == ['public', 'private']

        # Unauthorized user can only see public servers
        utils.set_logged_in_user('unauthuser')
        servers = account.util.get_servers()
        assert [s['server'] for s in servers] == ['public']


def test_help():
    """Test help page"""
    c = account.app.test_client()
    rv = c.get('/help')
    r = re.compile(b'Account Information.*Access Control',
                   re.DOTALL | re.MULTILINE)
    assert r.search(rv.data)


def test_contact():
    """Test contact page"""
    c = account.app.test_client()
    rv = c.get('/contact')
    r = re.compile(b'Contact.*modbase.*salilab\\.org',
                   re.DOTALL | re.MULTILINE)
    assert r.search(rv.data)


def test_register():
    """Test register page"""
    c = account.app.test_client()
    rv = c.get('/register')
    r = re.compile(b'Create an Account.*log on permanently',
                   re.DOTALL | re.MULTILINE)
    assert r.search(rv.data)


def test_register_not_academic():
    """Test registration failure (not academic)"""
    c = account.app.test_client()
    rv = c.post('/register', data={})
    r = re.compile(b'Error:.*only open for the academic community.*'
                   b'Create an Account',
                   re.DOTALL | re.MULTILINE)
    assert r.search(rv.data)


def test_register_short_password():
    """Test registration failure (password too short)"""
    c = account.app.test_client()
    rv = c.post('/register', data={'academic': 'on', 'password': 'short',
                                   'passwordcheck': 'short'})
    r = re.compile(b'Error:.*Passwords should be between 8 and 25 characters.*'
                   b'Create an Account',
                   re.DOTALL | re.MULTILINE)
    assert r.search(rv.data)


def test_register_mismatched_password():
    """Test registration failure (mismatched password)"""
    c = account.app.test_client()
    rv = c.post('/register', data={'academic': 'on', 'password': '12345678',
                                   'passwordcheck': 'not12345678'})
    r = re.compile(b'Error:.*The two passwords are not identical.*'
                   b'Create an Account',
                   re.DOTALL | re.MULTILINE)
    assert r.search(rv.data)


def test_register_missing_fields():
    """Test registration failure (missing fields)"""
    c = account.app.test_client()
    data = {'academic': 'on', 'password': '12345678',
            'passwordcheck': '12345678', 'modeller_key': 'modkey'}
    needed_fields = ('user_name', 'first_name', 'last_name',
                     'institution', 'email')
    for field in needed_fields:
        for f in needed_fields:
            data[f] = 'foo'
        data[field] = ''
        rv = c.post('/register', data=data)
        r = re.compile(b'Error:.*Please fill out all required form fields.*'
                       b'Create an Account',
                       re.DOTALL | re.MULTILINE)
        assert r.search(rv.data)


def test_register_existing_user():
    """Test registration failure (user name already exists)"""
    c = account.app.test_client()
    data = {'academic': 'on', 'password': '12345678',
            'passwordcheck': '12345678', 'user_name': 'authuser',
            'first_name': 'foo', 'last_name': 'foo', 'institution': 'foo',
            'email': 'foo', 'modeller_key': ''}
    rv = c.post('/register', data=data)
    r = re.compile(b'Error:.*User name authuser already exists.*'
                   b'Create an Account',
                   re.DOTALL | re.MULTILINE)
    assert r.search(rv.data)


def test_register_ok():
    """Test successful registration"""
    c = account.app.test_client()
    data = {'academic': 'on', 'password': '12345678',
            'passwordcheck': '12345678', 'user_name': 'newuser',
            'first_name': 'foo', 'last_name': 'foo', 'institution': 'foo',
            'email': 'foo', 'modeller_key': 'modkey'}
    rv = c.post('/register', data=data)
    assert rv.status_code == 302  # redirect to index page
    assert (rv.headers['Set-Cookie'] ==
            'sali-servers=user_name&newuser&session&'
            '25d55ad283aa400af464c76d713c07ad; Secure; HttpOnly; Path=/; '
            'SameSite=Lax')


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
    account.util.setup_logging(mock_app)
    assert mock_app.logger.h is not None


def test_logged_out_profile():
    """Test fail to edit profile when logged-out"""
    c = account.app.test_client()
    rv = c.get('/profile')
    assert rv.status_code == 403


def test_profile():
    """Test show of edit-profile page"""
    c = account.app.test_client()
    utils.set_servers_cookie(c, 'authuser', 'authpw00')
    rv = c.get('/profile', base_url='https://localhost')  # force HTTPS
    r = re.compile(b'Edit Profile.*'
                   b'first_name.*Auth.*'
                   b'last_name.*User.*'
                   b'institution.*Test In1.*'
                   b'email.*authuser@test\\.com.*'
                   b'license key.*authusermodkey',
                   re.DOTALL | re.MULTILINE)
    assert r.search(rv.data)


def test_profile_missing_fields():
    """Test edit-profile failure (missing fields)"""
    c = account.app.test_client()
    utils.set_servers_cookie(c, 'authuser', 'authpw00')
    data = {'modeller_key': ''}
    needed_fields = ('first_name', 'last_name',
                     'institution', 'email')
    for field in needed_fields:
        for f in needed_fields:
            data[f] = 'foo'
        data[field] = ''
        rv = c.post('/profile', data=data, base_url='https://localhost')
        r = re.compile(b'Edit Profile.*'
                       b'Error:.*Please fill out all required form fields.*',
                       re.DOTALL | re.MULTILINE)
        assert r.search(rv.data)


def test_profile_long_fields():
    """Test edit-profile failure (too-long fields)"""
    c = account.app.test_client()
    utils.set_servers_cookie(c, 'authuser', 'authpw00')
    fields = ('first_name', 'last_name',
              'institution', 'email', 'modeller_key')
    for field in fields:
        data = {}
        for f in fields:
            data[f] = 'foo'
        data[field] = 'x' * 80
        rv = c.post('/profile', data=data, base_url='https://localhost')
        r = re.compile(b'Edit Profile.*'
                       b'Error:.*Form field too long.*',
                       re.DOTALL | re.MULTILINE)
        assert r.search(rv.data)


def test_profile_ok():
    """Test successful edit-profile"""
    c = account.app.test_client()
    utils.set_servers_cookie(c, 'authuser', 'authpw00')
    # No change in data
    data = {'first_name': 'Auth', 'last_name': 'User',
            'institution': 'Test In1', 'email': 'authuser@test.com',
            'modeller_key': 'authusermodkey'}
    rv = c.post('/profile', data=data, base_url='https://localhost')
    assert rv.status_code == 302  # redirect to index page


def test_logged_out_password():
    """Test fail to change password when logged-out"""
    c = account.app.test_client()
    rv = c.get('/password')
    assert rv.status_code == 403


def test_password():
    """Test show of change-password page"""
    c = account.app.test_client()
    utils.set_servers_cookie(c, 'authuser', 'authpw00')
    rv = c.get('/password', base_url='https://localhost')  # force HTTPS
    r = re.compile(b'Change Password.*'
                   b'Current Password:.*'
                   b'New Password.*'
                   b'Re-enter Password:.*',
                   re.DOTALL | re.MULTILINE)
    assert r.search(rv.data)


def test_password_wrong_old():
    """Test change-password failure (wrong old password)"""
    c = account.app.test_client()
    utils.set_servers_cookie(c, 'authuser', 'authpw00')
    data = {'oldpassword': 'notauthpw', 'newpassword': '12345678',
            'passwordcheck': '12345678'}
    rv = c.post('/password', data=data, base_url='https://localhost')
    r = re.compile(b'Change Password.*'
                   b'Error:.*Incorrect old password entered.',
                   re.DOTALL | re.MULTILINE)
    assert r.search(rv.data)


def test_password_too_short():
    """Test change-password failure (new password too short)"""
    c = account.app.test_client()
    utils.set_servers_cookie(c, 'authuser', 'authpw00')
    data = {'oldpassword': 'authpw00', 'newpassword': '1234',
            'passwordcheck': '1234'}
    rv = c.post('/password', data=data, base_url='https://localhost')
    r = re.compile(b'Change Password.*'
                   b'Error:.*Passwords should be between 8 and 25 characters',
                   re.DOTALL | re.MULTILINE)
    assert r.search(rv.data)


def test_password_too_long():
    """Test change-password failure (new password too long)"""
    c = account.app.test_client()
    utils.set_servers_cookie(c, 'authuser', 'authpw00')
    data = {'oldpassword': 'authpw00', 'newpassword': 'x' * 30,
            'passwordcheck': 'x' * 30}
    rv = c.post('/password', data=data, base_url='https://localhost')
    r = re.compile(b'Change Password.*'
                   b'Error:.*Passwords should be between 8 and 25 characters',
                   re.DOTALL | re.MULTILINE)
    assert r.search(rv.data)


def test_password_mismatch():
    """Test change-password failure (new passwords do not match)"""
    c = account.app.test_client()
    utils.set_servers_cookie(c, 'authuser', 'authpw00')
    data = {'oldpassword': 'authpw00', 'newpassword': '12345678',
            'passwordcheck': 'not12345678'}
    rv = c.post('/password', data=data, base_url='https://localhost')
    r = re.compile(b'Change Password.*'
                   b'Error:.*The two passwords are not identical',
                   re.DOTALL | re.MULTILINE)
    assert r.search(rv.data)


def test_password_ok():
    """Test change-password success"""
    c = account.app.test_client()
    utils.set_servers_cookie(c, 'authuser', 'authpw00')
    # new password = old password
    data = {'oldpassword': 'authpw00', 'newpassword': 'authpw00',
            'passwordcheck': 'authpw00'}
    rv = c.post('/password', data=data, base_url='https://localhost')
    assert rv.status_code == 302  # redirect to index page


def test_reset_input():
    """Test reset page, asking for email input"""
    c = account.app.test_client()
    rv = c.get('/reset')
    r = re.compile(b'Password Reset.*'
                   b'To reset the password.*'
                   b'Email:.*Send reset email',
                   re.DOTALL | re.MULTILINE)
    assert r.search(rv.data)


def test_reset_send_mail_fail():
    """Test reset send email failure (no account matches)"""
    c = account.app.test_client()
    rv = c.post('/reset', data={'email': 'bademail@test.com'})
    r = re.compile(b'Password Reset.*'
                   b'Error:.*No account found with email bademail@test\\.com.*'
                   b'To reset the password.*',
                   re.DOTALL | re.MULTILINE)
    assert r.search(rv.data)


def test_reset_send_mail_fail_bad_recipient():
    """Test reset send email failure (bad recipient)"""
    c = account.app.test_client()
    rv = c.post('/reset', data={'email': 'badrecip@test.com'})
    r = re.compile(b'Password Reset.*'
                   b'Error:.*Failed to send a password reset email.*'
                   b'Please contact us so we can reset your password.*'
                   b'To reset the password.*',
                   re.DOTALL | re.MULTILINE)
    assert r.search(rv.data)


def test_reset_send_mail_ok():
    """Test reset send email success"""
    c = account.app.test_client()
    rv = c.post('/reset', data={'email': 'authuser@test.com'})
    r = re.compile(b'Password Reset.*'
                   b'reset link has been sent to authuser@test\\.com.*'
                   b'This link will expire in 2 days',
                   re.DOTALL | re.MULTILINE)
    assert r.search(rv.data)


def test_reset_link_input_fail():
    """Test reset link input page fail"""
    c = account.app.test_client()
    rv = c.get('/reset/3/unauthkey')
    r = re.compile(b'Password Reset.*'
                   b'Error.*Invalid password reset link',
                   re.DOTALL | re.MULTILINE)
    assert r.search(rv.data)


def test_reset_link_input_ok():
    """Test reset link input page success"""
    c = account.app.test_client()
    rv = c.get('/reset/2/unauthkey')
    r = re.compile(b'Password Reset.*'
                   b'Choose new password for user unauthuser.*'
                   b'Choose Password.*'
                   b'Re-enter Password.*',
                   re.DOTALL | re.MULTILINE)
    assert r.search(rv.data)


def test_reset_link_password_fail():
    """Test reset link failure, bad password"""
    c = account.app.test_client()
    rv = c.post('/reset/2/unauthkey',
                data={'password': 'abc', 'passwordcheck': 'abc'})
    r = re.compile(b'Password Reset.*'
                   b'Error:.*Passwords should be between 8 and 25 characters.*'
                   b'Choose Password.*'
                   b'Re-enter Password.*',
                   re.DOTALL | re.MULTILINE)
    assert r.search(rv.data)


def test_reset_link_password_ok():
    """Test reset link set password success"""
    c = account.app.test_client()
    rv = c.post('/reset/2/unauthkey',
                data={'password': 'unauthpw', 'passwordcheck': 'unauthpw'})
    assert rv.status_code == 302  # redirect to index page


def test_internal_error_handler():
    """Test that internal errors yield a custom 500 error page"""
    # Patch app to force an error
    old_rt = account.render_template

    def mock_render_template(fname, *args, **kwargs):
        if 'saliweb' in fname:
            return old_rt(fname, *args, **kwargs)
        else:
            raise ValueError()

    try:
        account.app.testing = False  # don't disable error handlers
        account.render_template = mock_render_template
        c = account.app.test_client()
        rv = c.get('/')
        assert rv.status_code == 500
        r = re.compile(b'500 Internal Server Error.*'
                       b'A fatal internal error occurred in this web service.*'
                       b'Apologies for the inconvenience',
                       re.DOTALL | re.MULTILINE)
        assert r.search(rv.data)
    finally:
        account.render_template = old_rt
        account.app.testing = True
