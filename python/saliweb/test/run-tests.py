import unittest
import sys
import os
import re


def regressionTest():
    modobjs = []
    for f in sys.argv[1:]:
        dir, mod = os.path.split(f)
        mod = os.path.splitext(mod)[0]
        sys.path.insert(0, dir)
        modobjs.append(__import__(mod))
        sys.path.pop(0)
    tests = [unittest.defaultTestLoader.loadTestsFromModule(o) \
             for o in modobjs]
    return unittest.TestSuite(tests)

if __name__ == "__main__":
    unittest.main(defaultTest="regressionTest", argv=[sys.argv[0], '-v'])
