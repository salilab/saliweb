import flask
import saliweb.frontend
from saliweb.frontend import Parameter, FileParameter


parameters = [Parameter("job_name", "Job name", optional=True),
              FileParameter("input_pdb", "PDB file to be refined")]
app = saliweb.frontend.make_application(__name__, parameters)
