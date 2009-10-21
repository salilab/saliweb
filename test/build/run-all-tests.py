import unittest, sys, os, re
import coverage

class RunAllTests(unittest.TestProgram):
    """Custom main program that also displays a final coverage report"""
    def __init__(self, *args, **keys):
        # Start coverage testing now before we import any modules
        coverage.start()

        # Run the tests
        unittest.TestProgram.__init__(self, *args, **keys)

    def runTests(self):
        self.testRunner = unittest.TextTestRunner(verbosity=self.verbosity)
        result = self.testRunner.run(self.test)
        coverage.stop()
        coverage.the_coverage.collect()
        coverage.use_cache(False)
        print >> sys.stderr, "\nPython coverage report\n"
        mods = ['python/saliweb/*.py', 'python/saliweb/build/*.py']
        coverage.the_coverage.relative_dir = 'python/'
        coverage.report(mods, file=sys.stderr)
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
