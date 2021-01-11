import unittest
import saliweb.backend


class LockedJobDictTest(unittest.TestCase):
    """Check the _LockedJobDict class"""

    def test_locked_job_dict(self):
        """Check the _LockedJobDict class"""
        d = saliweb.backend._LockedJobDict()
        self.assertRaises(KeyError, d.remove, 'bar')
        self.assertNotIn('foo', d)
        d.add('foo')
        self.assertIn('foo', d)
        d.remove('foo')
        self.assertNotIn('foo', d)
        self.assertRaises(KeyError, d.remove, 'foo')


if __name__ == '__main__':
    unittest.main()
