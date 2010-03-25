import unittest
import saliweb.backend.events

class EventsTest(unittest.TestCase):
    """Check events"""

    def test_event_queue(self):
        """Check the _EventQueue class"""
        e = saliweb.backend.events._EventQueue()
        self.assertEqual(e.get(0), None)
        e.put('a')
        e.put('b')
        self.assertEqual(e.get(), 'a')
        self.assertEqual(e.get(), 'b')
        self.assertEqual(e.get(0), None)

if __name__ == '__main__':
    unittest.main()
