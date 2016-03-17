from __future__ import print_function
from optparse import OptionParser
import saliweb.backend
import sys
import signal
import time
import os


def get_options():
    parser = OptionParser()
    parser.set_usage("""
%prog [-h] {start|stop|restart|condstart|status}

Start or stop the daemon that processes incoming, completed, and old jobs.

'condstart' only starts the daemon if it is currently stopped, and does nothing
if it is already running.
""")
    opts, args = parser.parse_args()
    if len(args) != 1:
        parser.error("Wrong number of arguments given")
    if args[0] not in ('start', 'stop', 'restart', 'condstart', 'status'):
        parser.error("service state not valid")
    return args[0]


def kill_pid(pid):
    for i in range(10):
        try:
            os.kill(pid, signal.SIGTERM)
            os.kill(pid, 0)
        except OSError:
            return True
        time.sleep(0.1)


def status(web):
    pid = web.get_running_pid()
    if pid is None:
        print("%s is stopped" % web.config.service_name)
        sys.exit(3)
    else:
        print("%s (pid %d) is running..." % (web.config.service_name, pid))


def stop(web):
    sys.stdout.write("Stopping %s: " % web.config.service_name)
    pid = web.get_running_pid()
    if pid is None:
        print("FAILED; not running")
        sys.exit(1)
    else:
        if kill_pid(pid):
            print("OK")
        else:
            print("FAILED; pid %d did not terminate" % pid)
            sys.exit(2)


def start(web):
    sys.stdout.write("Starting %s: " % web.config.service_name)
    web.do_all_processing(daemonize=True, status_fh=sys.stdout)


def condstart(web):
    sys.stdout.write("Starting %s: " % web.config.service_name)
    try:
        web.do_all_processing(daemonize=True, status_fh=sys.stdout)
    except saliweb.backend.StateFileError as detail:
        print("not started: " + str(detail))


def restart(web):
    stop(web)
    start(web)


def main(webservice):
    state = get_options()
    web = webservice.get_web_service(webservice.config)
    if state == 'status':
        status(web)
    elif state == 'start':
        start(web)
    elif state == 'stop':
        stop(web)
    elif state == 'condstart':
        condstart(web)
    elif state == 'restart':
        restart(web)
