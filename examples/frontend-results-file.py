@app.route('/job/<name>/<path:fp>')
def results_file(name, fp):
    job = saliweb.frontend.get_completed_job(name,
                                             flask.request.args.get('passwd'))
    if fp in ('output.pdb', 'log'):
        return flask.send_from_directory(job.directory, fp)
    else:
        flask.abort(404)
