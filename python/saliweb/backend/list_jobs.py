import saliweb.backend
from optparse import OptionParser
import sys


def get_options():
    parser = OptionParser()
    default_states = ['FAILED', 'INCOMING', 'PREPROCESSING',
                      'POSTPROCESSING', 'FINALIZING', 'RUNNING']
    parser.set_usage("""
%prog [-h] [STATE ...]

Print a list of all jobs in the given STATE(s).
If no states are given, the following are used by default:
""" + ", ".join(default_states))
    opts, args = parser.parse_args()
    if len(args) < 1:
        args = default_states
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
        for job in web.db._get_all_jobs_in_state(state, order_by='submit_time'):
            print("%-60s %s" % (job.name, state))
