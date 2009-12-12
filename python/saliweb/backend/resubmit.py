from optparse import OptionParser
import sys


def get_options():
    parser = OptionParser()
    parser.set_usage("""
%prog [-h] JOBNAME

Take the given failed job, JOBNAME, and put it back in the incoming queue.
""")
    opts, args = parser.parse_args()
    if len(args) != 1:
        parser.error("Need to specify a job name")
    return args[0]


def main(webservice):
    name = get_options()
    web = webservice.get_web_service(webservice.config)
    job = web.get_job_by_name('FAILED', name)
    if job:
        job.resubmit()
    else:
        print >> sys.stderr, "Could not find job", name
