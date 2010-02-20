import unittest
import time
import os
import signal
from saliweb.backend import LocalRunner

class LocalRunnerTest(unittest.TestCase):
    """Check LocalRunner class"""

    def test_run_poll(self):
        """Check that LocalRunner runs and polls processes successfully"""
        r = LocalRunner(['/bin/sleep', '60'])
        pid = r._run()
        self.assert_(isinstance(pid, str))
        self.assertEqual(LocalRunner._check_completed(pid), False)
        self.assertEqual(LocalRunner._children.keys(), [pid])
        os.kill(int(pid), signal.SIGTERM)
        time.sleep(0.1)
        # Make sure that non-zero return code causes a job failure
        self.assertRaises(OSError, LocalRunner._check_completed, pid)
        # Children should now be empty
        self.assertEqual(LocalRunner._children, {})

        # Check successful completion
        r = LocalRunner(['/bin/echo', 'foo'])
        pid = r._run()
        time.sleep(0.1)
        self.assertEqual(LocalRunner._check_completed(pid), True)
        self.assertEqual(LocalRunner._children, {})

    def test_run_proc(self):
        """Check that LocalRunner jobs from other processes are checked"""
        r = LocalRunner('/bin/sleep 60')
        pid = r._run()
        self.assertEqual(LocalRunner._check_completed(pid), False)
        # Make the LocalRunner fall back to its behavior for checking non-child
        # processes
        del LocalRunner._children[pid]
        self.assertEqual(LocalRunner._check_completed(pid), False)
        os.kill(int(pid), signal.SIGTERM)
        # Remove zombie process
        os.waitpid(int(pid), 0)
        self.assertEqual(LocalRunner._check_completed(pid), True)

if __name__ == '__main__':
    unittest.main()
