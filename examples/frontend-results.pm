sub get_results_page {
    my ($self, $job) = @_;
    my $q = $self->cgi;

    my $return = $q->p("Job '<b>" . $job->name . "</b>' has completed.");

    if (-f 'output.pdb') {
        $return .= $q->p("<a href=\"" . $q->self_url .
                         "&amp;file=output.pdb\">Download output PDB</a>.");
    } else {
        $return .= $q->p("No output PDB file was produced. Please inspect " .
                         "the log file to determine the problem.");
    }
    $return .= $q->p("<a href=\"" . $q->self_url .
                     "&amp;file=log\">Download log file</a>.");
    $return .= $job->get_results_available_time($q);
    return $return;
}

sub allow_file_download {
    my ($self, $file) = @_;
    return $file eq 'output.pdb' or $file eq 'log';
}
