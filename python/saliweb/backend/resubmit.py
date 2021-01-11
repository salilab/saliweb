from argparse import ArgumentParser
import sys


def get_options():
    parser = ArgumentParser(
        description="Take the given failed job(s), JOBNAME, and put "
                    "them back in the incoming queue.")
    parser.add_argument(
        "jobs", nargs="+", metavar="JOBNAME",
        help="Job(s) to resubmit")
    args = parser.parse_args()
    return args.jobs


def main(webservice):
    names = get_options()
    web = webservice.get_web_service(webservice.config)
    for name in names:
        job = web.get_job_by_name('FAILED', name)
        if job:
            job.resubmit()
        else:
            print("Could not find job", name, file=sys.stderr)
