package saliweb::frontend::RESTService;
use base 'saliweb::frontend';

sub rest_url {
    return "job.cgi";
}

# Replace HTML URLs with REST-style
sub _munge_url {
    my ($self, $url) = @_;
    my $from = $self->results_url;
    my $to = $self->rest_url;
    my $ind = index($url, $from);
    if ($ind < 0) {
        throw saliweb::frontend::InternalError(
              "Cannot find $from in results URL $url");
    } else {
        substr($url, $ind, length($from), $to);
        return $url;
    }
}

sub _display_web_page {
    my ($self, $content) = @_;
    my $q = $self->cgi;
    print $q->header('text/xml', $self->http_status) .
          "<?xml version=\"1.0\"?>\n" . $content;
}

sub format_fatal_error {
    my ($self, $exc) = @_;
    my $q = new CGI; # We may not have created $self->cgi yet
    my $status = "500 Internal Server Error";
    return $q->header('text/xml', $status) .
           "<?xml version=\"1.0\"?>\n" .
           "<error type=\"internal\">$exc</error>\n";
}

sub format_input_validation_error {
    my ($self, $exc) = @_;
    return "<error type=\"input_validation\">$exc</error>";
}

sub format_results_error {
    my ($self, $exc) = @_;
    return "<error type=\"results\">$exc</error>";
}

sub _internal_display_submit_page {
    my ($self, $content, $submitted_jobs) = @_;
    my $text = "";
    for my $job (@$submitted_jobs) {
        $text .= "<job xlink:href=\"" . $self->_munge_url($job->results_url) .
                 "\"/>\n";
    }

    $self->_display_web_page($text);
}

sub _display_results_page_index {
    my ($self, $contents, $jobobj) = @_;
    my $text = "<results_files>\n";
    for my $job (@{$jobobj->{results}}) {
        $text .= "   <results_file xlink:href=\"" .
                 $self->_munge_url($job->{url}) . "\">" .
                 $job->{name} . "</results_file>\n";
    }
    $text .= "</results_files>\n";
    $self->_display_web_page($text);
}

1;
