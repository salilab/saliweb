import saliweb.backend
from optparse import OptionParser
import sys


def get_options():
    parser = OptionParser()
    parser.set_usage("""
%prog [-h] STATE [STATE ...]

Print a list of all jobs in the given STATE(s).
""")
    opts, args = parser.parse_args()
    if len(args) < 1:
        parser.error("Need to specify at least one job state")
    return args

def check_valid_state(state):
    # Check for valid state name
    return saliweb.backend._JobState(state)

def main(webservice):
    states = get_options()
    for state in states:
        check_valid_state(state)
    web = webservice.get_web_service(webservice.config)
    for state in states:
        print "All jobs in %s state" % state
        for job in web.db._get_all_jobs_in_state(state):
            print "    ", job.name
