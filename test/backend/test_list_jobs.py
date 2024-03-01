import unittest
import sys
from saliweb.backend import InvalidStateError
from saliweb.backend.list_jobs import check_valid_state, get_options, main
from io import StringIO


class Tests(unittest.TestCase):

    def test_check_valid_state(self):
        """Test check_valid_state function"""
        self.assertRaises(InvalidStateError, check_valid_state, 'garbage')
        self.assertRaises(InvalidStateError, check_valid_state, 'failed')
        for state in ('FAILED', 'EXPIRED', 'COMPLETED', 'RUNNING'):
            check_valid_state(state)

    def test_get_options(self):
        """Test list_jobs get_options()"""
        def run_get_options(args):
            old = sys.argv
            oldstderr = sys.stderr
            try:
                sys.stderr = StringIO()
                sys.argv = ['testprogram'] + args
                return get_options()
            finally:
                sys.stderr = oldstderr
                sys.argv = old
        states = run_get_options(['FAILED', 'RUNNING'])
        self.assertEqual(states, ['FAILED', 'RUNNING'])

    def test_main(self):
        """Test list_jobs main()"""
        class DummyJob(object):
            def __init__(self, name):
                self.name = name

        class DummyDatabase(object):
            def _get_all_jobs_in_state(self, state, order_by):
                if state == 'FAILED':
                    return [DummyJob('foo'), DummyJob('bar')]
                elif state == 'PREPROCESSING':
                    return [DummyJob('testpre')]
                elif state == 'RUNNING':
                    return [DummyJob('baz')]
                else:
                    return []

        class DummyWebService(object):
            def __init__(self, mod):
                self.mod = mod
                self.db = DummyDatabase()

        class DummyModule(object):
            config = 'testconfig'
            job_deleted = False

            def get_web_service(self, config):
                return DummyWebService(self)

        old = sys.argv
        oldout = sys.stdout
        try:
            sio = StringIO()
            sys.stdout = sio
            mod = DummyModule()
            sys.argv = ['testprogram', 'FAILED', 'RUNNING']
            main(mod)
            self.assertEqual(
                sio.getvalue(),
                "%-60s FAILED\n"
                "%-60s FAILED\n"
                "%-60s RUNNING\n" % ('foo', 'bar', 'baz'))
            sio = StringIO()
            sys.stdout = sio
            mod = DummyModule()
            sys.argv = ['testprogram']
            main(mod)
            self.assertEqual(
                sio.getvalue(),
                "%-60s FAILED\n"
                "%-60s FAILED\n"
                "%-60s PREPROCESSING\n"
                "%-60s RUNNING\n" % ('foo', 'bar', 'testpre', 'baz'))
        finally:
            sys.argv = old
            sys.stdout = oldout


if __name__ == '__main__':
    unittest.main()
