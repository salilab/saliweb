import saliweb.backend
from optparse import OptionParser
import sys


def get_options():
    parser = OptionParser()
    parser.set_usage("""
%prog [-h] [-f] STATE JOBNAME [...]

Delete the job(s) JOBNAME in the given STATE.

STATE must be either FAILED or EXPIRED if the backend daemon is running.
Jobs in other states can only be deleted if the backend is stopped first.
""")
    parser.add_option("-f", "--force", action="store_true",
                      default=False, dest="force",
                      help="Delete jobs without prompting")
    opts, args = parser.parse_args()
    if len(args) < 2:
        parser.error("Need to specify a state and at least one job name")
    return args[0], args[1:], opts


def delete_job(job, force):
    if not force:
        sys.stdout.write("Delete job %s? " % job.name)
        sys.stdout.flush()
        reply = sys.stdin.readline()
        if len(reply) < 1 or reply[0].upper() != 'Y':
            return
    job.delete()


def check_valid_state(web, state):
    # Check for valid state name
    jobstate = saliweb.backend._JobState(state)
    pid = web.get_running_pid()
    if pid is not None and state not in ("FAILED", "EXPIRED"):
        raise ValueError("Cannot delete jobs in %s state while the backend "
                         "is running. Please stop the backend first" % state)


def main(webservice):
    state, job_names, opts = get_options()
    web = webservice.get_web_service(webservice.config)
    check_valid_state(web, state)
    for name in job_names:
        job = web.get_job_by_name(state, name)
        if job:
            delete_job(job, opts.force)
        else:
            print("Could not find job", name, file=sys.stderr)
