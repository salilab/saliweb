import saliweb.backend
from argparse import ArgumentParser
import sys


def get_options():
    parser = ArgumentParser(
            description="Force the job(s) JOBNAME into the FAILED state. "
                "This can only be done if the backend daemon is stopped first. "
                "By default, the server admin will receive an email for each "
                "failed job, just as if it failed \"normally\". This can be "
                "suppressed with the -n option.")
    parser.add_argument("jobnames", nargs="+", metavar="JOBNAME",
            help="Job(s) to fail")

    parser.add_argument("-n", "--no-email", action="store_false",
            default=True, dest="email",
            help="Don't email the admin about the failed job")
    parser.add_argument("-f", "--force", action="store_true",
            default=False, dest="force", help="Fail jobs without prompting")

    return parser.parse_args()


def fail_job(job, force, email):
    if not force:
        sys.stdout.write("Fail job %s? " % job.name)
        sys.stdout.flush()
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
    args = get_options()
    web = webservice.get_web_service(webservice.config)
    check_daemon_running(web)
    all_states = saliweb.backend._JobState.get_valid_states()
    for name in args.jobnames:
        job = find_job(web, name, all_states)
        if job:
            fail_job(job, args.force, args.email)
        else:
            print("Could not find job", name, file=sys.stderr)
