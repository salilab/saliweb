import unittest
from saliweb.backend import _JobState, InvalidStateError

class StatesTest(unittest.TestCase):
    """Check _JobState state machine"""

    def test_create_state(self):
        """Check making new _JobState objects"""
        for state in ('INCOMING', 'FAILED', 'RUNNING'):
            j = _JobState(state)
        self.assertRaises(InvalidStateError, _JobState, 'garbage')

    def test_get(self):
        """Check _JobState.get()"""
        for state in ('INCOMING', 'FAILED', 'RUNNING'):
            j = _JobState(state)
            self.assertEqual(j.get(), state)

    def test_get_valid_states(self):
        """Check _JobState.get_valid_states()"""
        states = _JobState.get_valid_states()
        self.assertEqual(len(states), 8)
        self.assertEqual(states[0], 'INCOMING')

    def test_transition(self):
        """Check _JobState.transition()"""
        valid = [['INCOMING', 'PREPROCESSING'], ['ARCHIVED', 'EXPIRED'],
                 ['RUNNING', 'FAILED'], ['FAILED', 'INCOMING']]
        invalid = [['INCOMING', 'RUNNING'], ['INCOMING', 'garbage']]
        for instate, outstate in valid:
            j = _JobState(instate)
            j.transition(outstate)
            self.assertEqual(j.get(), outstate)
        for instate, outstate in invalid:
            j = _JobState(instate)
            self.assertRaises(InvalidStateError, j.transition, outstate)

if __name__ == '__main__':
    unittest.main()
