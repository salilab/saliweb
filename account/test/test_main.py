import utils

utils.set_search_paths(__file__)
import account


def test_index():
    """Test index page"""
    account.app.testing = True
    c = account.app.test_client()
    rv = c.get('/')
    assert rv.status_code == 200
