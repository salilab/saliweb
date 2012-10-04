import unittest, sys, os, re
import glob

# Only use coverage if it's new enough and is requested
try:
    import coverage
    if not hasattr(coverage.coverage, 'combine'):
        coverage = None
except ImportError:
    coverage = None
if 'SALIWEB_COVERAGE' not in os.environ:
    coverage = None

class RunAllTests(unittest.TestProgram):
    """Custom main program that also displays a final coverage report"""
    def __init__(self, *args, **keys):
        if coverage:
            # Start coverage testing now before we import any modules
            self.topdir = 'python'
            self.mods = glob.glob("%s/saliweb/*.py" % self.topdir) \
                        + glob.glob("%s/saliweb/backend/*.py" % self.topdir)

            self.cov = coverage.coverage(branch=True, include=self.mods,
                                         data_file='.coverage.backend')
            self.cov.start()

        # Run the tests
        unittest.TestProgram.__init__(self, *args, **keys)

    def runTests(self):
        self.testRunner = unittest.TextTestRunner(verbosity=self.verbosity)
        result = self.testRunner.run(self.test)

        if coverage:
            self.cov.stop()
            self.cov.combine()
            self.cov.use_cache(True)
            print >> sys.stderr, "\nPython coverage report\n"

            self.cov.file_locator.relative_dir = self.topdir + '/'
            self.cov.report(self.mods, file=sys.stderr)
            self.cov.save()

        sys.exit(not result.wasSuccessful())

def regressionTest():
    try:
        os.unlink('state_file')
    except OSError:
        pass
    path = os.path.abspath(os.path.dirname(sys.argv[0]))
    files = os.listdir(path)
    test = re.compile("^test_.*\.py$", re.IGNORECASE)
    files = filter(test.search, files)
    modnames = [os.path.splitext(f)[0] for f in files]

    modobjs = [__import__(m) for m in modnames]
    tests = [unittest.defaultTestLoader.loadTestsFromModule(o) for o in modobjs]
    return unittest.TestSuite(tests)

if __name__ == "__main__":
    RunAllTests(defaultTest="regressionTest")
