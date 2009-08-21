import unittest
from saliweb.backend import JobState, InvalidStateError

class StatesTest(unittest.TestCase):
    """Check JobState state machine"""

    def test_create_state(self):
        """Check making new JobState objects"""
        for state in ('INCOMING', 'FAILED', 'RUNNING'):
            j = JobState(state)
        self.assertRaises(InvalidStateError, JobState, 'garbage')

    def test_get(self):
        """Check JobState.get()"""
        for state in ('INCOMING', 'FAILED', 'RUNNING'):
            j = JobState(state)
            self.assertEqual(j.get(), state)

    def test_get_valid_states(self):
        """Check JobState.get_valid_states()"""
        states = JobState.get_valid_states()
        self.assertEqual(len(states), 8)
        self.assertEqual(states[0], 'INCOMING')

    def test_transition(self):
        """Check JobState.transition()"""
        valid = [['INCOMING', 'PREPROCESSING'], ['ARCHIVED', 'EXPIRED'],
                 ['RUNNING', 'FAILED'], ['FAILED', 'INCOMING']]
        invalid = [['INCOMING', 'RUNNING'], ['INCOMING', 'garbage']]
        for instate, outstate in valid:
            j = JobState(instate)
            j.transition(outstate)
            self.assertEqual(j.get(), outstate)
        for instate, outstate in invalid:
            j = JobState(instate)
            self.assertRaises(InvalidStateError, j.transition, outstate)

if __name__ == '__main__':
    unittest.main()
