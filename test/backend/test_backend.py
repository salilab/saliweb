from __future__ import print_function
import saliweb.backend
import unittest


class Tets(unittest.TestCase):
    def test_sigterm_handler(self):
        """Test sigterm_handler"""
        self.assertRaises(saliweb.backend._SigTermError,
                          saliweb.backend._sigterm_handler, None, None)


if __name__ == '__main__':
    unittest.main()
