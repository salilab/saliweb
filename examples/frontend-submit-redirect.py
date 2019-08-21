@app.route('/job', methods=['GET', 'POST'])
def job():
    if flask.request.method == 'GET':
        return saliweb.frontend.render_queue_page()
    else:
        return submit_new_job()


@app.route('/job/<name>')
def results(name):
    job = get_completed_job(name, request.args.get('passwd'),
                            still_running_template='running.html')
    ...  # as for the previous results page, above


def submit_new_job():
    ...  # as for the previous submit page, above

    job.submit(email)

    # Go straight to the results page
    return saliweb.frontend.redirect_to_results_page(job)
