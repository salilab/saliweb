import unittest
import os
from saliweb.backend import _DelayFileStream
from testutil import RunInTempDir

class LoggingTest(unittest.TestCase):
    """Check job logging"""

    def test_init(self):
        """Check create of _DelayFileStream objects"""
        d = RunInTempDir()
        dfs = _DelayFileStream('foo')
        self.assertEqual(dfs.filename, os.path.join(d.tmpdir, 'foo'))
        self.assertEqual(dfs.stream, None)
        self.assertEqual(os.path.exists('foo'), False)
        # flush should be a no-op
        dfs.flush()
        self.assertEqual(os.path.exists('foo'), False)
        # File should appear on the first write
        print >> dfs, "test text"
        dfs.flush()
        self.assertEqual(os.path.exists('foo'), True)
        contents = open('foo').read()
        self.assertEqual(contents, 'test text\n')

if __name__ == '__main__':
    unittest.main()
