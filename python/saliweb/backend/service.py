from argparse import ArgumentParser
import saliweb.backend
import sys
import signal
import time
import os


def get_options():
    parser = ArgumentParser(
        description="Start or stop the daemon that processes incoming, "
                    "completed, and old jobs.")
    parser.add_argument("state",
            choices=['start', 'stop', 'restart', 'condstart', 'status'],
            help="'condstart' only starts the daemon if it is currently "
                 "stopped, and does nothing if it is already running")
    return parser.parse_args().state


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
