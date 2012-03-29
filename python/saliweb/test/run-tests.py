import unittest
import sys
import os
import re
from optparse import OptionParser
import glob

# Only use coverage if it's new enough
try:
    import coverage
    if not hasattr(coverage.coverage, 'combine'):
        coverage = None
except ImportError:
    coverage = None

class RunAllTests(unittest.TestProgram):
    """Custom main program that also displays a final coverage report"""
    def __init__(self, opts, *args, **keys):
        self.opts = opts
        if coverage:
            # Start coverage testing now before we import any modules
            cwd = os.path.dirname(sys.argv[0])
            self.topdir = os.path.abspath(os.path.join(cwd, 'python'))
            self.mods = glob.glob("%s/*/*.py" % self.topdir)

            self.cov = coverage.coverage(branch=True, include=self.mods)
            self.cov.start()

        # Run the tests
        unittest.TestProgram.__init__(self, *args, **keys)

    def runTests(self):
        self.testRunner = unittest.TextTestRunner(verbosity=self.verbosity)
        result = self.testRunner.run(self.test)

        if coverage:
            self.cov.stop()
            self.cov.combine()
            self.cov.use_cache(False)
            print >> sys.stderr, "\nPython coverage report\n"

            self.cov.file_locator.relative_dir = self.topdir + '/'
            self.cov.report(self.mods, file=sys.stderr)
            html = self.opts.html_coverage
            if html:
                self.cov.html_report(self.mods,
                                     directory=os.path.join(html, 'python'))
            for cov in glob.glob('.coverage.*'):
                os.unlink(cov)
        sys.exit(not result.wasSuccessful())


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

def parse_options():
    parser = OptionParser()
    parser.add_option("--html_coverage", dest="html_coverage", type="string",
                      default=None,
                      help="directory to write HTML coverage info into")
    return parser.parse_args()

if __name__ == "__main__":
    opts, args = parse_options()
    sys.argv = [sys.argv[0], '-v'] + args
    RunAllTests(opts, defaultTest="regressionTest")
