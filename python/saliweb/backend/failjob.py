from __future__ import print_function
import saliweb.backend
from optparse import OptionParser
import sys


def get_options():
    parser = OptionParser()
    parser.set_usage("""
%prog [-h] [-n] JOBNAME [...]

Force the job(s) JOBNAME into the FAILED state.

This can only be done if the backend daemon is stopped first.
By default, the server admin will receive an email for each failed job, just
as if it failed "normally". This can be suppressed with the -n option.
""")
    parser.add_option("-n", "--no-email", action="store_false",
                      default=True, dest="email",
                      help="Don't email the admin about the failed job")
    parser.add_option("-f", "--force", action="store_true",
                      default=False, dest="force",
                      help="Fail jobs without prompting")
    opts, args = parser.parse_args()
    if len(args) < 1:
        parser.error("Need to specify at least one job name")
    return args, opts


def fail_job(job, force, email):
    if not force:
        sys.stdout.write("Fail job %s? " % job.name)
        reply = sys.stdin.readline()
        if len(reply) < 1 or reply[0].upper() != 'Y':
            return
    job.admin_fail(email)


def check_daemon_running(web):
    pid = web.get_running_pid()
    if pid is not None:
        raise ValueError("Cannot fail jobs while the backend is running. "
                         "Please stop the backend first")


def find_job(web, name, all_states):
    """Find a job in any state"""
    for state in all_states:
        job = web.get_job_by_name(state, name)
        if job:
            return job


def main(webservice):
    job_names, opts = get_options()
    web = webservice.get_web_service(webservice.config)
    check_daemon_running(web)
    all_states = saliweb.backend._JobState.get_valid_states()
    for name in job_names:
        job = find_job(web, name, all_states)
        if job:
            fail_job(job, opts.force, opts.email)
        else:
            print("Could not find job", name, file=sys.stderr)
