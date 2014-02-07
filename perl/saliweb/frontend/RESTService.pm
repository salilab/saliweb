package saliweb::frontend::RESTService;
use base 'saliweb::frontend';

sub rest_url {
    my $self = shift;
    return $self->cgiroot . "/job";
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
          "<?xml version=\"1.0\"?>\n" .
          "<saliweb xmlns:xlink=\"http://www.w3.org/1999/xlink\">\n" .
          $content .
          "</saliweb>\n";
}

sub format_fatal_error {
    my ($self, $exc) = @_;
    my $q = new CGI; # We may not have created $self->cgi yet
    my $status = "500 Internal Server Error";
    return $q->header('text/xml', $status) .
           "<?xml version=\"1.0\"?>\n" .
           "<saliweb xmlns:xlink=\"http://www.w3.org/1999/xlink\">\n" .
           "   <error type=\"internal\">$exc</error>\n" .
           "</saliweb>\n";
}

sub format_user_error {
    my ($self, $exc) = @_;
    my $msg = $exc->text;
    my $type = "user";
    if ($exc->isa("saliweb::frontend::InputValidationError")) {
        $type = "input_validation";
    }
    return "   <error type=\"$type\">$msg</error>";
}

sub format_results_error {
    my ($self, $exc) = @_;
    my $msg = $exc->text;
    my $ret = "   <error type=\"results\">$msg</error>\n";
    if ($exc->isa('saliweb::frontend::ResultsBadURLError')) {
        $ret .= $self->get_help();
    }
    return $ret;
}

sub get_help {
    my $self = shift;
    my $service = $self->{server_name};
    $service =~ s/&/&amp;/g;
    my $cgiroot = $self->cgiroot;
    my $rest_url = $self->rest_url;
    my $help = <<END;
   <service name="$service" />
   <help>
<p>
This URL provides a REST-style interface to the Sali Lab's $service
web service. It is designed to be used for automated job submission
and collection of job results.
</p>

<p>
If you want to use the web interface for this service instead, please
open $cgiroot in a web browser.
</p>

<p>
To submit a job to the service, use the web_service.py tool available
at http://modbase.compbio.ucsf.edu/web_service.py
</p>

<p>
Alternatively, submit an HTTP POST request to
$rest_url
</p>

<p>
The POST data should be encoded as multipart/form-data and include the same
options and uploaded files that are submitted by the web interface. The service
will return a simple XML file that contains a URL for the completed job, which
will look like
$rest_url/jobname
</p>

<p>
If an error occurs, a suitable HTTP status code will be set and the XML
file will contain a human-readable error string.
</p>

<p>
To retrieve job results, submit an HTTP GET request to the previously-obtained
URL. If the job is not yet complete an HTTP status code is returned; otherwise,
a simple XML file containing a list of the job's output files is returned.
Each output file is named with a URL of the form
$rest_url/jobname/outputfile
and the file itself can be obtained by a GET request to that URL.
</p>
   </help>
END
    my $parameters = $self->get_submit_parameter_help();
    $help .= "\n   <parameters>\n" . join("\n", @$parameters)
             . "\n   </parameters>\n";
    return $help;
}

sub _internal_display_submit_page {
    my ($self, $content, $submitted_jobs) = @_;
    my $text = "";
    for my $job (@$submitted_jobs) {
        $text .= "   <job xlink:href=\"" .
                 $self->_munge_url($job->results_url) . "\"/>\n";
    }

    $self->_display_web_page($text);
}

sub _display_results_page_index {
    my ($self, $contents, $jobobj) = @_;
    for my $metadata (@{$jobobj->{metadata}}) {
        if ($metadata->{type} eq "link") {
            $text .= "   <$metadata->{key} xlink:href=\"" . $metadata->{value}
                     . "\" />\n";
        } else {
            $text .= "   <$metadata->{key}>" . $metadata->{value}
                     . "</$metadata->{key}>\n";
        }
    }
    for my $job (@{$jobobj->{results}}) {
        $text .= "   <results_file xlink:href=\"" .
                 $self->_munge_url($job->{url}) . "\">" .
                 $job->{name} . "</results_file>\n";
    }
    $self->_display_web_page($text);
}

1;
