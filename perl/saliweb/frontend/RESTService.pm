package saliweb::frontend::RESTService;
use base 'saliweb::frontend';

sub _display_web_page {
    my ($self, $content) = @_;
    my $q = $self->cgi;
    print $q->header('text/xml', $status) .
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

sub _internal_display_submit_page {
    my ($self, $content, $submitted_jobs) = @_;
    my $q = $self->cgi;
    my $text = "";
    for my $job (@$submitted_jobs) {
        $text .= "<job xlink:href=\"" . $job->results_url . "\"/>\n";
    }

    $self->_display_web_page($text);
}

1;
