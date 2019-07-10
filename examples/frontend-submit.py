@app.route('/job', methods=['GET', 'POST'])
def job():
    if flask.request.method == 'GET':
        return saliweb.frontend.render_queue_page()
    else:
        return submit_new_job()


def submit_new_job():
    # Get form parameters
    input_pdb = flask.request.files.get('input_pdb')
    job_name = flask.request.form.get('job_name') or 'job'
    email = flask.request.form.get('email')

    # Validate input
    file_contents = input_pdb.readlines()
    atoms = 0
    for line in file_contents:
        if line.startswith('ATOM  '):
            atoms += 1
    if atoms == 0:
        raise saliweb.frontend.InputValidationError(
                   "PDB file contains no ATOM records!")

    # Create job directory, add input files, then submit the job
    job = saliweb.frontend.IncomingJob(job_name)

    with open(job.get_path('input.pdb'), 'w') as fh:
        fh.writelines(file_contents)

    job.submit(email)

    # Inform the user of the job name and results URL
    return saliweb.frontend.render_submit_template(
        'submit.html', email=email, job=job)
