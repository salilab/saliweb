import saliweb.backend
from argparse import ArgumentParser
import sys


def get_options():
    parser = ArgumentParser(
        description="Delete the job(s) JOBNAME in the given STATE.")
    parser.add_argument("state", metavar="STATE", help="Job state to consider")
    parser.add_argument(
        "jobs", metavar="JOBNAME", nargs="+", help="Jobs to delete")
    parser.add_argument(
        '-f', "--force", action="store_true",
        default=False, dest="force",
        help="Delete jobs without prompting")

    args = parser.parse_args()
    return args.state, args.jobs, args.force


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
    _ = saliweb.backend._JobState(state)
    pid = web.get_running_pid()
    if pid is not None and state not in ("FAILED", "EXPIRED"):
        raise ValueError("Cannot delete jobs in %s state while the backend "
                         "is running. Please stop the backend first" % state)


def main(webservice):
    state, job_names, force = get_options()
    web = webservice.get_web_service(webservice.config)
    check_valid_state(web, state)
    for name in job_names:
        job = web.get_job_by_name(state, name)
        if job:
            delete_job(job, force)
        else:
            print("Could not find job", name, file=sys.stderr)
