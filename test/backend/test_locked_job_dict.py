import unittest
import saliweb.backend

class LockedJobDictTest(unittest.TestCase):
    """Check the _LockedJobDict class"""

    def test_locked_job_dict(self):
        """Check the _LockedJobDict class"""
        d = saliweb.backend._LockedJobDict()
        self.assertRaises(KeyError, d.remove, 'bar')
        self.assertEquals('foo' in d, False)
        d.add('foo')
        self.assertEquals('foo' in d, True)
        d.remove('foo')
        self.assertEquals('foo' in d, False)
        self.assertRaises(KeyError, d.remove, 'foo')

if __name__ == '__main__':
    unittest.main()
