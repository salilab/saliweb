from optparse import OptionParser
import saliweb.backend
import sys

def get_options():
    parser = OptionParser()
    parser.set_usage("""
%prog [-h] [-v]

Do any necessary processing of incoming, completed, or old jobs.
""")
    parser.add_option('-v', '--verbose', action="store_true", dest="verbose",
                      help="""Print verbose output""")
    opts, args = parser.parse_args()
    if len(args) != 0:
        parser.error("Extra arguments given")
    return opts

def main(webservice):
    opts = get_options()
    web = webservice.get_web_service(webservice.config)
    try:
        web.do_all_processing()
    except saliweb.backend.StateFileError, detail:
        if opts.verbose:
            raise
        # else ignore the exception
