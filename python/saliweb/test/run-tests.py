from __future__ import print_function
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
        data = '.coverage.frontend' if opts.frontend else '.coverage.backend'
        for cov in glob.glob(data + '*'):
            os.unlink(cov)
        if coverage:
            # Start coverage testing now before we import any modules
            self.subdir = 'frontend' if opts.frontend else 'backend'
            self.topdir = os.path.abspath(os.path.join(os.getcwd(),
                                                       self.subdir))
            # Handle old-style backend location if necessary
            if not os.path.exists(self.topdir):
                self.subdir = 'python'
                self.topdir = os.path.abspath(os.path.join(os.getcwd(),
                                                           self.subdir))
            self.mods = glob.glob("%s/*/*.py" % self.topdir)

            self.cov = coverage.coverage(branch=True, include=self.mods,
                                         data_file=data)

            self.cov.start()

        # Run the tests
        unittest.TestProgram.__init__(self, *args, **keys)

    def runTests(self):
        self.testRunner = unittest.TextTestRunner(verbosity=self.verbosity)
        result = self.testRunner.run(self.test)

        if coverage:
            self.cov.stop()
            self.cov.save()
            self.cov.use_cache(False)
            print("\nPython coverage report\n", file=sys.stderr)

            if hasattr(coverage.files, 'RELATIVE_DIR'):
                coverage.files.RELATIVE_DIR = self.topdir + '/'
            else:
                self.cov.file_locator.relative_dir = self.topdir + '/'
            self.cov.report(self.mods, file=sys.stderr)
            html = self.opts.html_coverage
            if html:
                self.cov.html_report(self.mods,
                    directory=os.path.join(html, self.subdir))
            if not self.opts.coverage:
                for cov in glob.glob('.coverage*'):
                    os.unlink(cov)
        sys.exit(not result.wasSuccessful())

def get_boilerplate_test_case(module_name):
    service = __import__(module_name)
    import saliweb.backend
    import saliweb.test

    class BoilerplateTests(saliweb.test.TestCase):
        """Check required web service 'boilerplate' functions"""

        def test_get_web_service(self):
            """Check get_web_service function"""
            import saliweb.backend
            def db_init(self, jobobj):
                self.jobobj = jobobj
            def config_init(self, configfile):
                self.configfile = configfile
            def ws_init(self, config, db):
                self.config = config
                self.db = db
            config = 'testconfig'
            old_db = saliweb.backend.Database.__init__
            old_config = saliweb.backend.Config.__init__
            old_ws = saliweb.backend.WebService.__init__
            try:
                saliweb.backend.Database.__init__ = db_init
                saliweb.backend.Config.__init__ = config_init
                saliweb.backend.WebService.__init__ = ws_init
                w = service.get_web_service(config)
            finally:
                saliweb.backend.Database.__init__ = old_db
                saliweb.backend.Config.__init__ = old_config
                saliweb.backend.WebService.__init__ = old_ws
            self.assertEqual(w.config.configfile, 'testconfig')
            self.assertTrue(issubclass(w.db.jobobj, saliweb.backend.Job),
                            "%s is not a Job subclass" % w.db.jobobj)
    return BoilerplateTests(methodName='test_get_web_service')


def get_all_tests():
    module_name = sys.argv[1]
    modobjs = []
    for f in sys.argv[2:]:
        dir, mod = os.path.split(f)
        mod = os.path.splitext(mod)[0]
        sys.path.insert(0, dir)
        modobjs.append(__import__(mod))
        sys.path.pop(0)
    tests = [unittest.defaultTestLoader.loadTestsFromModule(o) \
             for o in modobjs]
    return tests, module_name


def regressionTestBackend():
    tests, module_name = get_all_tests()
    tests.append(get_boilerplate_test_case(module_name))
    return unittest.TestSuite(tests)


def regressionTestFrontend():
    tests, module_name = get_all_tests()
    return unittest.TestSuite(tests)


def parse_options():
    parser = OptionParser()
    parser.add_option("--html_coverage", dest="html_coverage", type="string",
                      default=None,
                      help="directory to write HTML coverage info into")
    parser.add_option("--coverage", dest="coverage",
                      default=False, action="store_true",
                      help="preserve output coverage files")
    parser.add_option("--frontend", dest="frontend",
                      default=False, action="store_true",
                      help="test frontend rather than backend")
    return parser.parse_args()

if __name__ == "__main__":
    opts, args = parse_options()
    sys.argv = [sys.argv[0]] + args
    # Get directory containing test files
    os.environ['SALIWEB_TESTDIR'] = os.path.abspath(os.path.dirname(args[-1]))
    end = 'Frontend' if opts.frontend else 'Backend'
    RunAllTests(opts, defaultTest="regressionTest%s" % end,
                argv=[sys.argv[0], '-v'])
