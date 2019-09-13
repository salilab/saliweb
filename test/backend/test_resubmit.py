import unittest
import sys
from saliweb.backend.resubmit import main
if sys.version_info[0] >= 3:
    from io import StringIO
else:
    from io import BytesIO as StringIO


class ResubmitTest(unittest.TestCase):
    """Check resubmit script"""

    def test_main(self):
        """Test resubmit main()"""
        class DummyJob(object):
            def __init__(self, mod):
                self.mod = mod
            def resubmit(self):
                self.mod.job_resub = True
        class DummyWebService(object):
            def __init__(self, mod):
                self.mod = mod
            def get_job_by_name(self, state, name):
                if state == 'FAILED' and name == 'testjob':
                    return DummyJob(self.mod)
                else:
                    return None
        class DummyModule(object):
            config = 'testconfig'
            job_resub = False
            def get_web_service(self, config):
                return DummyWebService(self)

        old = sys.argv
        olderr = sys.stderr
        try:
            sys.stderr = StringIO()
            mod = DummyModule()
            sys.argv = ['testprogram']
            self.assertRaises(SystemExit, main, mod)

            sio = StringIO()
            sys.stderr = sio
            mod = DummyModule()
            sys.argv = ['testprogram'] + ['badjob']
            main(mod)
            self.assertEqual(sio.getvalue(), 'Could not find job badjob\n')
            self.assertEqual(mod.job_resub, False)

            sio = StringIO()
            sys.stderr = sio
            mod = DummyModule()
            sys.argv = ['testprogram'] + ['testjob']
            main(mod)
            self.assertEqual(sio.getvalue(), '')
            self.assertEqual(mod.job_resub, True)
        finally:
            sys.argv = old
            sys.stderr = olderr


if __name__ == '__main__':
    unittest.main()
