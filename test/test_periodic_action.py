import unittest
from saliweb.backend import _PeriodicAction
import time

class TestMethod(object):
    def __init__(self):
        self.called = False
    def __call__(self):
        self.called = True
    def assertCalled(self, testobj):
        testobj.assert_(self.called)
        self.called = False
    def assertNotCalled(self, testobj):
        testobj.assert_(not self.called)

class PeriodicActionTest(unittest.TestCase):
    """Check _PeriodicAction class"""

    def test_init(self):
        """Check creation of _PeriodicAction objects"""
        p = _PeriodicAction(10, 'foo')
        self.assertEqual(p.interval, 10)
        self.assertEqual(p.meth, 'foo')
        self.assertEqual(p.last_time, 0.0)

    def test_get_time_to_next(self):
        """Check _PeriodicAction.get_time_to_next() method"""
        p = _PeriodicAction(10, 'foo')
        timenow = time.time()
        self.assertEqual(p.get_time_to_next(timenow), 0.0)
        p.last_time = timenow
        self.assertEqual(p.get_time_to_next(timenow), 10.0)
        self.assertEqual(p.get_time_to_next(timenow + 4.0), 6.0)

    def test_try_action(self):
        """Check _PeriodicAction.try_action() method"""
        timenow = time.time()
        m = TestMethod()
        p = _PeriodicAction(10, m)
        p.try_action(timenow)
        m.assertCalled(self)
        p.try_action(timenow)
        m.assertNotCalled(self)

    def test_reset(self):
        """Check _PeriodicAction.reset() method"""
        timenow = time.time()
        p = _PeriodicAction(10, 'foo')
        self.assertEqual(p.last_time, 0.0)
        p.reset()
        diff = p.last_time - timenow
        self.assert_(diff >= 0 and diff <= 0.05,
                     "last_time (%f) != timenow (%f)" % (p.last_time, timenow))

if __name__ == '__main__':
    unittest.main()
