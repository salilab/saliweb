from __future__ import print_function
import unittest
import os
from saliweb.backend import _DelayFileStream
import testutil

class LoggingTest(unittest.TestCase):
    """Check job logging"""

    @testutil.run_in_tempdir
    def test_init(self):
        """Check create of _DelayFileStream objects"""
        dfs = _DelayFileStream('foo')
        self.assertEqual(dfs.filename, os.path.join(os.getcwd(), 'foo'))
        self.assertIsNone(dfs.stream)
        self.assertFalse(os.path.exists('foo'))
        # flush should be a no-op
        dfs.flush()
        self.assertFalse(os.path.exists('foo'))
        # File should appear on the first write
        print("test text", file=dfs)
        dfs.flush()
        self.assertTrue(os.path.exists('foo'))
        contents = open('foo').read()
        self.assertEqual(contents, 'test text\n')

if __name__ == '__main__':
    unittest.main()
