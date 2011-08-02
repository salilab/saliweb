from optparse import OptionParser
import sys


def get_options():
    parser = OptionParser()
    parser.set_usage("""
%prog [-h] JOBNAME [...]

Take the given failed job(s), JOBNAME, and put them back in the incoming queue.
""")
    opts, args = parser.parse_args()
    if len(args) < 1:
        parser.error("Need to specify a job name")
    return args


def main(webservice):
    names = get_options()
    web = webservice.get_web_service(webservice.config)
    for name in names:
        job = web.get_job_by_name('FAILED', name)
        if job:
            job.resubmit()
        else:
            print >> sys.stderr, "Could not find job", name
