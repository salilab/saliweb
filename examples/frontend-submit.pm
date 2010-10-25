sub get_submit_page {
    my $self = shift;
    my $q = $self->cgi;

    # Get form parameters
    my $input_pdb = $q->upload('input_pdb');
    my $job_name = $q->param('job_name') || 'job';
    my $email = $q->param('email') || '';

    # Validate input
    my $file_contents = "";
    my $atoms = 0;
    while (<$input_pdb>) {
        if (/^ATOM  /) { $atoms++; }
        $file_contents .= $_;
    }
    if ($atoms == 0) {
        throw saliweb::frontend::InputValidationError(
                   "PDB file contains no ATOM records!");
    }

    # Create job directory, add input files, then submit the job
    my $job = $self->make_job($job_name);

    my $input_pdb = $job->directory . "/input.pdb";
    open(INPDB, "> $input_pdb")
       or throw saliweb::frontend::InternalError("Cannot open $input_pdb: $!");
    print INPDB $file_contents;
    close INPDB
       or throw saliweb::frontend::InternalError("Cannot close $input_pdb: $!");

    $job->submit($email);

    # Inform the user of the job name and results URL
    return $q->p("Your job " . $job->name . " has been submitted.") .
           $q->p("Results will be found at <a href=\"" .
                 $job->results_url . "\">this link</a>.");
}
