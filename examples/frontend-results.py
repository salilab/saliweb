@app.route('/job/<name>')
def results(name):
    job = saliweb.frontend.get_completed_job(name,
                                             flask.request.args.get('passwd'))
    # Determine whether the job completed successfully
    if os.path.exists(job.get_path('output.pdb')):
        template = 'results_ok.html'
    else:
        template = 'results_failed.html'
    return saliweb.frontend.render_results_template(template, job=job)
