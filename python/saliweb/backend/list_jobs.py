import saliweb.backend
from argparse import ArgumentParser
import sys


def get_options():
    parser = ArgumentParser(
            description="Print a list of all jobs in the given STATE(s).")
    parser.add_argument("states", metavar="STATE", nargs="*",
            help="States to consider. If no states are given, the following "
                 "are used by default: %(default)s",
            default=['FAILED', 'INCOMING', 'PREPROCESSING', 'POSTPROCESSING',
                     'FINALIZING', 'RUNNING'])
    return parser.parse_args().states

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
