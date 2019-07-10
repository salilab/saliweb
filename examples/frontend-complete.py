from flask import render_template, request
import saliweb.frontend


app = saliweb.frontend.make_application(__name__)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/job', methods=['GET', 'POST'])
def job():
    # submit new job or show all jobs (queue)


@app.route('/job/<name>')
def results(name):
    # show results page


@app.route('/job/<name>/<path:fp>')
def results_file(name, fp):
    # download results file
