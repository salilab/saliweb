import flask
import saliweb.frontend


parameters = [...]
app = saliweb.frontend.make_application(__name__, parameters)
