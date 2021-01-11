import unittest
import sys
from saliweb.backend.service import get_options, kill_pid, status, stop
from saliweb.backend.service import start, condstart, restart, main
from saliweb.backend import StateFileError
import saliweb.backend.service
if sys.version_info[0] >= 3:
    from io import StringIO
else:
    from io import BytesIO as StringIO


class DummyService(object):
    def __init__(self, pid):
        class DummyConfig(object):
            service_name = 'testservice'
        self.config = DummyConfig()
        self.pid = pid

    def get_running_pid(self):
        return self.pid

    def do_all_processing(self, daemonize=False, status_fh=None):
        if self.pid == 'bad_state':
            raise StateFileError('bad state')
        elif self.pid == 'other_error':
            raise ValueError()


class ServiceTest(unittest.TestCase):
    """Check service script"""

    def test_get_options(self):
        """Test service get_options()"""
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
        self.assertRaises(SystemExit, run_get_options, [])
        self.assertRaises(SystemExit, run_get_options, ['badaction'])
        self.assertEqual(run_get_options(['start']), 'start')

    def test_kill_pid(self):
        """Test service kill_pid()"""
        class DummyOSModule(object):
            kill_attempts = 0

            def kill(self, pid, sig):
                if sig == 0:
                    if pid == 'kill_first':
                        raise OSError()
                    elif pid == 'kill_second' and self.kill_attempts == 2:
                        raise OSError()
                else:
                    self.kill_attempts += 1
        oldos = saliweb.backend.service.os
        try:
            saliweb.backend.service.os = DummyOSModule()
            self.assertEqual(kill_pid('kill_first'), True)
            saliweb.backend.service.os = DummyOSModule()
            self.assertEqual(kill_pid('kill_second'), True)
        finally:
            saliweb.backend.service.os = oldos

    def test_status(self):
        """Test service status()"""
        old = sys.stdout
        try:
            sys.stdout = sio = StringIO()
            w = DummyService(1234)
            status(w)
            self.assertEqual(sio.getvalue(),
                             'testservice (pid 1234) is running...\n')

            sys.stdout = sio = StringIO()
            w = DummyService(None)
            self.assertRaises(SystemExit, status, w)
            self.assertEqual(sio.getvalue(), 'testservice is stopped\n')
        finally:
            sys.stdout = old

    def test_stop(self):
        """Test service stop()"""
        def dummy_kill_pid(pid):
            return pid == 1234
        old = sys.stdout
        oldkill = saliweb.backend.service.kill_pid
        try:
            saliweb.backend.service.kill_pid = dummy_kill_pid

            sys.stdout = sio = StringIO()
            w = DummyService(None)
            self.assertRaises(SystemExit, stop, w)
            self.assertEqual(sio.getvalue(),
                             'Stopping testservice: FAILED; not running\n')

            sys.stdout = sio = StringIO()
            w = DummyService(1234)
            stop(w)
            self.assertEqual(sio.getvalue(), 'Stopping testservice: OK\n')

            sys.stdout = sio = StringIO()
            w = DummyService(9999)
            self.assertRaises(SystemExit, stop, w)
            self.assertEqual(sio.getvalue(),
                             'Stopping testservice: FAILED; pid 9999 '
                             'did not terminate\n')
        finally:
            sys.stdout = old
            saliweb.backend.service.kill_pid = oldkill

    def test_start(self):
        """Test service start() and condstart()"""
        old = sys.stdout
        try:
            w = DummyService('bad_state')
            sys.stdout = sio = StringIO()
            self.assertRaises(StateFileError, start, w)
            self.assertEqual(sio.getvalue(), 'Starting testservice: ')

            # condstart should swallow, but report, the exception
            sys.stdout = sio = StringIO()
            condstart(w)
            self.assertEqual(sio.getvalue(),
                             'Starting testservice: not started: bad state\n')

            # other exceptions should not be swallowed
            w = DummyService('other_error')
            for meth in start, condstart:
                sys.stdout = sio = StringIO()
                self.assertRaises(ValueError, meth, w)
                self.assertEqual(sio.getvalue(), 'Starting testservice: ')
        finally:
            sys.stdout = old

    def test_restart(self):
        """Test service restart()"""
        events = []

        def dummy_stop(w):
            events.append('stop ' + w)

        def dummy_start(w):
            events.append('start ' + w)
        oldstart = saliweb.backend.service.start
        oldstop = saliweb.backend.service.stop
        try:
            saliweb.backend.service.start = dummy_start
            saliweb.backend.service.stop = dummy_stop
            restart('dummy')
            self.assertEqual(events, ['stop dummy', 'start dummy'])
        finally:
            saliweb.backend.service.start = oldstart
            saliweb.backend.service.stop = oldstop

    def test_main(self):
        """Test service main()"""
        events = []

        class DummyAction(object):
            def __init__(self, name):
                self.name = name

            def __call__(self, w):
                events.append(self.name + ' ' + w.config.service_name)

        class DummyModule(object):
            config = 'dummyconfig'

            def get_web_service(self, config):
                return DummyService(1234)

        actions = ['status', 'start', 'stop', 'condstart', 'restart']
        old = {}
        for a in actions:
            old[a] = getattr(saliweb.backend.service, a)
        oldarg = sys.argv
        try:
            for a in actions:
                setattr(saliweb.backend.service, a, DummyAction(a))
            for a in actions:
                sys.argv = ['testprogram', a]
                main(DummyModule())
                self.assertEqual(events.pop(), a + ' testservice')
        finally:
            sys.argv = oldarg
            for a in actions:
                setattr(saliweb.backend.service, a, old[a])


if __name__ == '__main__':
    unittest.main()
