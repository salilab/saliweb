import unittest
from saliweb.backend import InvalidStateError
from saliweb.backend.deljob import check_valid_state

class DummyWeb(object):
    def __init__(self, pid):
        self.pid = pid
    def get_running_pid(self):
        return self.pid

class DelJobTest(unittest.TestCase):
    """Check deljob script"""

    def test_check_valid_state(self):
        """Test check_valid_state function"""
        web = DummyWeb(None)
        self.assertRaises(InvalidStateError, check_valid_state, web, 'garbage')
        self.assertRaises(InvalidStateError, check_valid_state, web, 'failed')
        for state in ('FAILED', 'EXPIRED', 'COMPLETED', 'RUNNING'):
            check_valid_state(web, state)

        # Only FAILED/EXPIRED OK if the web service is running
        web = DummyWeb(999)
        for state in ('FAILED', 'EXPIRED'):
            check_valid_state(web, state)
        for state in ('COMPLETED', 'RUNNING'):
            self.assertRaises(ValueError, check_valid_state, web, state)

if __name__ == '__main__':
    unittest.main()
