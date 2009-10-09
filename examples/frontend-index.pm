sub get_index_page {
    my $self = shift;
    my $q = $self->cgi;

    return $q->start_form({-name=>'modfooform', -method=>'post',
                           -action->$self->submit_url}) .
           $q->p("Job name (optional)") .
           $q->textfield({-name=>'job_name'}) .
           $q->p("Email address (optional)") .
           $q->textfield({-name=>'email'}) .
           $q->p("Upload PDB file") .
           $q->filefield({-name=>'input_pdb'}) .
           $q->end_form;
}
