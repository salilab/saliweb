package saliweb::frontend::IncomingJob;

use IO::Socket;
use Fcntl ':flock';
use File::Path 'rmtree';

sub new {
    my ($invocant, $frontend, $given_name, $email) = @_;
    my $class = ref($invocant) || $invocant;
    my $self = {};
    bless($self, $class);
    $self->{frontend} = $frontend;
    $self->{email} = $email;
    ($self->{name}, $self->{directory}) = _get_job_name_directory($frontend,
                                                                  $given_name);
    $self->{frontend}->_add_incoming_job($self);
    return $self;
}

sub resume {
    my ($invocant, $frontend, $name) = @_;
    my $class = ref($invocant) || $invocant;
    my $self = {};
    bless($self, $class);
    $self->{frontend} = $frontend;
    $name = _sanitize_jobname($name);
    my $config = $frontend->{'config'};
    my $dbh = $frontend->{'dbh'};

    ($self->{name}, $self->{directory}) = _get_resumed_job($name, $dbh,
                                                           $config);
    $self->{frontend}->_add_incoming_job($self);
    return $self;
}

sub name {
    my $self = shift;
    return $self->{name};
}

sub directory {
    my $self = shift;
    return $self->{directory};
}

sub results_url {
    my $self = shift;
    my $url = $self->{url};
    if (!defined($url)) {
      throw saliweb::frontend::InternalError(
                     "Cannot get results URL before job is submitted");
    } else {
      return $url;
    }
}

sub _cancel {
    # Cancel a job rather than submitting it; clean up the directory
    my $self = shift;
    if (rmtree($self->{directory}) == 0) {
        die "Cannot remove directory " . $self->{directory} . ": $!";
    }
}

sub submit {
  my $self = shift;
  my $email = shift;
  my $config = $self->{frontend}->{'config'};
  my $dbh = $self->{frontend}->{'dbh'};

  if (defined($email)) {
    $self->{email} = $email;
  }

  ($self->{url}, $self->{passwd}) = _generate_results_url($self->{frontend},
                                                          $self->{name});

  # Insert row into database table
  my $query = "insert into jobs (name,passwd,user,contact_email,directory," .
              "url,submit_time) VALUES(?, ?, ?, ?, ?, ?, UTC_TIMESTAMP())";
  my $in = $dbh->prepare($query)
           or throw saliweb::frontend::DatabaseError(
                               "Cannot prepare query ". $dbh->errstr);
  $in->execute($self->{name}, $self->{passwd}, $self->{frontend}->{user_name},
               $self->{email}, $self->{directory}, $self->{url})
        or throw saliweb::frontend::DatabaseError(
                               "Cannot execute query ". $dbh->errstr);

  # Use socket to inform backend of new incoming job
  my $s = IO::Socket::UNIX->new(Peer=>$config->{general}->{'socket'},
                                Type=>SOCK_STREAM);
  if (defined($s)) {
    flock($s, LOCK_EX);
    print $s "INCOMING " . $self->{name};
    flock($s, LOCK_UN);
    $s->close();
  }
  $self->{frontend}->_add_submitted_job($self);
  $self->{frontend}->_remove_incoming_job($self);
}

sub _sanitize_jobname {
    my $jobname = shift;
    # Provide default
    $jobname = $jobname || "job";
    # Remove potentially dodgy characters in jobname
    $jobname =~ s/[^a-zA-Z0-9_-]//g;
    # Make sure jobname fits in the db (plus extra space for
    # auto-generated suffix if needed)
    $jobname = substr($jobname, 0, 30);
    return $jobname;
}

sub _get_job_name_directory {
  my ($frontend, $user_jobname) = @_;
  my $config = $frontend->{'config'};
  my $dbh = $frontend->{'dbh'};

  $user_jobname = _sanitize_jobname($user_jobname);

  my $query = $dbh->prepare('select count(name) from jobs where name=?')
                 or throw saliweb::frontend::DatabaseError(
                             "Cannot prepare query ". $dbh->errstr);
  my ($jobname, $jobdir);
  $jobdir = try_job_name($user_jobname, $query, $dbh, $config);
  if ($jobdir) {
    return ($user_jobname, $jobdir);
  }
  for (my $tries = 0; $tries < 50; $tries++) {
    $jobname = $user_jobname . "_" . int(rand(100000)) . $tries;
    $jobdir = try_job_name($jobname, $query, $dbh, $config);
    if ($jobdir) {
      return ($jobname, $jobdir);
    }
  }
  throw saliweb::frontend::InternalError(
                     "Could not determine a unique job name");
}

sub _generate_results_url {
    my ($frontend, $jobname) = @_;
    my $passwd = &generate_random_passwd(10);
    $url = $frontend->results_url . "/$jobname?passwd=$passwd";
    return ($url, $passwd);
}

sub generate_random_passwd {
  # Generate a random alphanumeric password of the given length
  my ($len) = @_;
  my @validchars = ('a'..'z', 'A'..'Z', 0..9);
  my $randstr = join '', map $validchars[rand @validchars], 1..$len;
  return $randstr;
}

sub _get_job_directory {
  my ($jobname, $config) = @_;
  return $config->{directories}->{INCOMING} . "/" . $jobname;
}

sub _get_resumed_job {
  my ($jobname, $dbh, $config) = @_;
  my $jobdir = _get_job_directory($jobname, $config);

  # Job directory must already exist and not be in the database
  if (! -d $jobdir) {
    throw saliweb::frontend::InputValidationError("Invalid job name provided");
  }

  my $query = $dbh->prepare('select count(name) from jobs where name=?')
               or throw saliweb::frontend::DatabaseError(
                           "Cannot prepare query ". $dbh->errstr);
  $query->execute($jobname)
       or throw saliweb::frontend::DatabaseError(
                               "Cannot execute: " . $dbh->errstr);
  my @data = $query->fetchrow_array();
  if ($data[0] == 0) {
    return ($jobname, $jobdir);
  } else {
    throw saliweb::frontend::InputValidationError("Invalid job name provided");
  }
}

sub try_job_name {
  my ($jobname, $query, $dbh, $config) = @_;
  my $jobdir = _get_job_directory($jobname, $config);
  if (-d $jobdir) {
    return;
  }
  $query->execute($jobname)
         or throw saliweb::frontend::DatabaseError(
                                 "Cannot execute: " . $dbh->errstr);
  my @data = $query->fetchrow_array();
  if ($data[0] == 0) {
    mkdir($jobdir) or throw saliweb::frontend::InternalError(
                            "Cannot make job directory $jobdir: $!");
    $query->execute($jobname)
         or throw saliweb::frontend::DatabaseError(
                                 "Cannot execute: " . $dbh->errstr);
    @data = $query->fetchrow_array();
    if ($data[0] == 0) {
      return $jobdir;
    }
  }
  return undef;
}

package saliweb::frontend::CompletedJob;

use Time::Local;

sub new {
    my ($invocant, $frontend, $job_row) = @_;
    my $class = ref($invocant) || $invocant;
    my %hash = %$job_row;
    my $self = \%hash;
    $self->{frontend} = $frontend;
    $self->{results} = [];
    for my $timename ('submit', 'preprocess', 'run', 'postprocess', 'end',
                      'archive', 'expire') {
        my $key = "${timename}_time";
        $self->{$key} = _to_unix_time($self->{$key});
    }
    bless($self, $class);
    return $self;
}

sub name {
    my $self = shift;
    return $self->{name};
}

sub directory {
    my $self = shift;
    return $self->{directory};
}

sub unix_archive_time {
    my $self = shift;
    return $self->{archive_time};
}

sub to_archive_time {
    my $self = shift;
    return _format_timediff($self->{archive_time});
}

sub get_results_available_time {
    my $self = shift;
    my $toarc = $self->to_archive_time;
    if ($toarc) {
        my $q = $self->{frontend}->{CGI};
        return $q->p("Job results will be available at this URL for $toarc.");
    } else {
        return "";
    }
}

sub results_url {
    my $self = shift;
    my $jobname = $self->{name};
    my $passwd = $self->{passwd};
    return $self->{frontend}->results_url . "/$jobname?passwd=$passwd";
}

sub get_results_file_url {
    my ($self, $file) = @_;
    my $jobname = $self->{name};
    my $passwd = $self->{passwd};
    my $url = $self->{frontend}->results_url . "/$jobname/$file?passwd=$passwd";
    push @{$self->{results}}, {name=>$file, url=>$url};
    return $url;
}

sub _format_timediff_unit {
    my ($timediff, $unit) = @_;
    my $strrep = sprintf "%d", $timediff;
    my $suffix = ($timediff eq "1" ? "" : "s");
    return "$strrep ${unit}${suffix}";
}

sub _format_timediff {
    my $timediff = shift;
    if (!defined($timediff)) {
        return undef;
    }
    $timediff -= time;
    if ($timediff < 0) {
        return undef;
    }
    if ($timediff < 120) {
        return _format_timediff_unit($timediff, "second");
    }
    $timediff /= 60.0;
    if ($timediff < 120) {
        return _format_timediff_unit($timediff, "minute");
    }
    $timediff /= 60.0;
    if ($timediff < 48) {
        return _format_timediff_unit($timediff, "hour");
    }
    $timediff /= 24.0;
    return _format_timediff_unit($timediff, "day");
}

sub _to_unix_time {
    my $db_utc_time = shift;
    if (!defined($db_utc_time)) {
        return undef;
    } elsif ($db_utc_time =~ /^(\d+)\-(\d+)\-(\d+) (\d+):(\d+):(\d+)$/) {
        return timegm($6, $5, $4, $3, $2 - 1, $1);
    } else {
        throw saliweb::frontend::InternalError(
                                     "Cannot parse time $db_utc_time");
    }
}


package saliweb::frontend;

use saliweb::server qw(validate_user);

require Exporter;
@ISA = qw(Exporter);
@EXPORT = qw(check_optional_email check_required_email check_modeller_key
             get_pdb_code get_pdb_chains);

# Location of our PDB mirror.
our $pdb_root = "/netapp/database/pdb/remediated/pdb/";

use File::Spec;
use DBI;
use CGI;
use Error qw(:try);
use MIME::Lite;
use Fcntl ':flock';

our $web_server = 'modbase.compbio.ucsf.edu';

sub new {
    my ($invocant, $config_file, $version, $server_name, $frontend) = @_;
    my $class = ref($invocant) || $invocant;
    my $self = {};
    bless($self, $class);
    $self->{server_name} = $server_name;
    $self->{version} = $version;
    $self->{rate_limit_period} = 3600;
    $self->{rate_limit} = 10;
    try {
        $self->{'CGI'} = $self->_setup_cgi();
        $self->{page_title} = $server_name;
        # Read configuration file
        $self->{'config'} = my $config = read_config($config_file, $frontend);
        my $urltop = $config->{general}->{urltop};
        # Make sure any links we generate are also secure if we are secure
        if ($self->cgi->https) {
            $urltop =~ s/^http:/https:/;
        }
        $self->{http_status} = undef;
        $self->{'htmlroot'} = $urltop . "/html/";
        $self->{'cgiroot'} = $urltop;
        $self->{'dbh'} = my $dbh = connect_to_database($config);
        $self->_setup_user($dbh);
    } catch Error with {
        $self->handle_fatal_error(shift);
    };
    return $self;
}

sub _admin_email {
    my $self = shift;
    if (defined($self->{config}) && defined($self->{config}->{general})
        && defined($self->{config}->{general}->{admin_email})) {
        return $self->{config}->{general}->{admin_email};
    } else {
        # If an error occurred before we managed to read the configuration file,
        # fall back to bothering the sysadmins
        return "system\@salilab.org";
    }
}

sub format_fatal_error {
    my ($self, $exc) = @_;
    my $q = new CGI; # We may not have created $self->cgi yet
    my $status = "500 Internal Server Error";
    return $q->header(-status=>$status) .
           $q->start_html(-title => $status) .
           $q->h1($status) .
           $q->p("A fatal internal error occurred in this web service. ". 
                 "We have been notified of the problem, and should " .
                 "fix it shortly.") .
           $q->p("For your reference, the error message reported is below:") .
           $q->pre($exc) .
           $q->p("Apologies for the inconvenience.") .
           $q->end_html;
}

sub handle_fatal_error {
    my ($self, $exc) = @_;
    print $self->format_fatal_error($exc);

    $self->_email_admin_fatal_error($exc);

    # Rethrow the error to terminate the process
    $exc->throw();
}

sub handle_user_error {
    my ($self, $exc) = @_;
    $self->http_status($exc->http_status);
    my $content = $self->format_user_error($exc);
    $self->_display_web_page($content);
}

sub _check_rate_limit {
    my $self = shift;
    my $file = "/tmp/" . lc($self->{server_name}) . "-service.state";
    my $period = $self->{rate_limit_period};
    my $limit = $self->{rate_limit};

    # Get timestamp of start of rate period, and number of errors during that
    # period, from the state file (if it does not exist, assume 0,0).
    # Lock it to ensure consistency.
    open(FH, '+>>', $file) or die "Cannot open $file: $!";
    flock(FH, LOCK_EX);
    seek(FH, 0, 0);
    my $line = <FH>;
    my $start_time = my $count = 0;
    if (defined($line) and $line =~ /^(\d+)\t(\d+)$/) {
        ($start_time, $count) = ($1, $2);
    }
    my $current_time = time();

    # Reset the count if the period has elapsed
    if ($current_time - $start_time > $period) {
        $start_time = $current_time;
        $count = 1;
    }

    # Update the file with new count
    truncate FH, 0;
    printf FH "$start_time\t%d\n", $count + 1;
    flock(FH, LOCK_UN);
    close FH or die "Cannot close file: $!";

    return ($count, $limit, $period);
}

sub _email_admin_fatal_error {
    my ($self, $exc) = @_;

    my ($count, $limit, $period) = $self->_check_rate_limit();
    if ($count > $limit) {
        # Don't send email if we've hit the rate limit, to avoid overloading
        # the mail server (and the server admin!)
        return;
    }

    # Don't bother the admin with client errors
    if ($exc =~ /^CGI\.pm: Server closed socket during multipart read/) {
        return;
    }

    my $subject = "Fatal error in " .  $self->{server_name} .
                  " web service frontend";
    my $data = <<END;
A fatal error occurred in the $self->{server_name} web service frontend.
Please correct this problem as soon as possible, as it prevents end users
from being able to use your web service.

The specific error message is shown below:
$exc
END

    if ($count == $limit) {
        $data .= "\n\n" . <<END;
These emails are rate-limited to $limit every $period seconds, and with
this email that limit has been reached. Thus, further errors for up to
$period seconds will not trigger additional emails.
END
    }

    my $admin_email = $self->_admin_email;
    my $msg = MIME::Lite->new(From => $admin_email,
                              To => $admin_email,
                              Subject => $subject,
                              Data => $data);
    # If an error occurs here, there's not much we can do about it, so ignore it
    $msg->send();
}

sub htmlroot {
    my $self = shift;
    return $self->{'htmlroot'};
}

sub cgiroot {
    my $self = shift;
    return $self->{'cgiroot'};
}

sub dbh {
    my $self = shift;
    return $self->{'dbh'};
}

sub http_status {
    my $self = shift;
    if (@_) { $self->{http_status} = shift; }
    return $self->{http_status};
}

sub cgi {
    my $self = shift;
    return $self->{CGI};
}

sub version {
    my $self = shift;
    return $self->{version};
}

sub user_name {
    my $self = shift;
    return $self->{user_name};
}

sub email {
    my $self = shift;
    if (defined($self->{'user_info'})) {
        return $self->{'user_info'}->{'email'};
    } else {
        return undef;
    }
}

sub modeller_key {
    # Right now user_info does not contain the Modeller key, but when it does,
    # this should function like email(), above.
    return undef;
}

sub index_url {
    my $self = shift;
    return $self->cgiroot . "/";
}

sub submit_url {
    my $self = shift;
    return $self->cgiroot . "/submit.cgi";
}

sub queue_url {
    my $self = shift;
    return $self->cgiroot . "/queue.cgi";
}

sub help_url {
    my $self = shift;
    return $self->cgiroot . "/help.cgi?type=help";
}

sub news_url {
    my $self = shift;
    return $self->cgiroot . "/help.cgi?type=news";
}

sub faq_url {
    my $self = shift;
    return $self->cgiroot . "/help.cgi?type=faq";
}

sub contact_url {
    my $self = shift;
    return $self->cgiroot . "/help.cgi?type=contact";
}

sub links_url {
    my $self = shift;
    return $self->cgiroot . "/help.cgi?type=links";
}

sub about_url {
    my $self = shift;
    return $self->cgiroot . "/help.cgi?type=about";
}

sub results_url {
    my $self = shift;
    return $self->cgiroot . "/results.cgi";
}

sub download_url {
    my $self = shift;
    return $self->cgiroot . "/download.cgi";
}

sub set_page_title {
    my ($self, $title) = @_;
    $self->{page_title} = $self->{server_name} . " " . $title;
}

sub _setup_cgi {
    my $q = new CGI;
    # Handle a CGI error if one occurred
    my $error = $q->cgi_error;
    if ($error) {
        print $q->header(-status=>$error),
              $q->start_html('CGI error encountered'),
              $q->h2('CGI error encountered'),
              $q->strong($error),
              $q->end_html;
        exit 0;
    } else {
        return $q;
    }
}

sub _setup_user {
    my ($self, $dbh) = @_;
    my $q = $self->cgi;

    # No user logged in by default
    $self->{'user_name'} = undef;
    $self->{'user_info'} = undef;

    # Only try to get user information if we are SSL-secured
    if (!$q->https) { return; }

    my %cookie = $q->cookie('sali-servers');
    if ($cookie{'user_name'}) {
        my ($user_name, $hash, $user_info) =
            &validate_user($dbh, 'servers', 'hash', $cookie{'user_name'},
                           $cookie{'session'});
        if (($user_name ne "not validated") && ($user_name ne "")
            && ($user_name) && $user_name ne "Anonymous") {
            $self->{'user_name'} = $user_name;
            $self->{'user_info'} = $user_info;
        }
    }
}

sub start_html {
    my ($self, $style) = @_;
    my $q = $self->{'CGI'};
    $style = $style || "/saliweb/css/server.css";
    return $q->header(-status => $self->http_status) .
           $q->start_html($self->get_start_html_parameters($style));
}

=item get_start_html_parameters
Get parameters to be used to call CGI.pm's start_html() method.
Can be customized in a derived class to add extra stylesheets or scripts,
for example.
=cut
sub get_start_html_parameters {
    my ($self, $style) = @_;

    return (-title => $self->{page_title},
            -style => {-src=>[$style]},
            -script=>[{-language => 'JavaScript',
                       -src=>"/saliweb/js/salilab.js"}]);
}

sub end_html {
    my ($self) = @_;
    my $q = $self->{'CGI'};
    return $q->end_html;
}

sub get_projects {
    my %projects;
    return \%projects;
}

=item get_project_menu
Return an HTML fragment which will be displayed in a project menu, used by
get_header(). This can contain general information about the service, links,
etc., and should be overridden for each service.
=cut
sub get_project_menu {
    return "";
}

=item get_header_page_title
Return the HTML fragment used to display the page title inside a div in
the page header. By default, this just displays the lab logo and the page
title, but can be overridden if desired.
=cut
sub get_header_page_title {
    my $self = shift;
    return '<h3><img src="http://salilab.org/img/logo_small.gif" height="40" ' .
           'alt="" />' . $self->{page_title} . '</h3>';
}

=item get_lab_navigation_links
Return a reference to a list of links to other lab resources and services,
used by get_header(). This can be overridden in subclasses to add additional
links.
=cut
sub get_lab_navigation_links {
    my $self = shift;
    my $q = $self->cgi;
    return [
        $q->a({-href=>'http://salilab.org/'}, "Sali Lab Home"),
        $q->a({-href=>'http://salilab.org/modweb/'}, "ModWeb"),
        $q->a({-href=>'http://salilab.org/modbase/'}, "ModBase"),
        $q->a({-href=>'http://salilab.org/modeval/'}, "ModEval"),
        $q->a({-href=>'http://salilab.org/pcss/'}, "PCSS"),
        $q->a({-href=>'http://salilab.org/foxs/'}, "FoXS"),
        $q->a({-href=>'http://salilab.org/imp/'}, "IMP"),
        $q->a({-href=>'http://salilab.org/multifit/'}, "MultiFit"),
        $q->a({-href=>'http://salilab.org/modpipe/'}, "ModPipe")
    ];
}

=item get_navigation_links
Return a reference to a list of navigation links, used by get_header().
This should be overridden for each service to add links to pages to submit
jobs, show help, list jobs in the queue, etc.
=cut
sub get_navigation_links {
    return [];
}

sub get_header {
    my $self = shift;
    my $q = $self->{'CGI'};
    my $projects = $self->get_projects();
    my $project_menu = $self->get_project_menu();
    my $lab_navigation_links = $self->get_lab_navigation_links();
    my $navigation_links = $self->get_navigation_links();
    if ($self->{'user_info'}) {
        my $user_name = $self->{'user_name'};
        unshift @$navigation_links,
              $q->a({-href=>"https://$web_server/scgi/server.cgi?logout=true"},
                    "Logout");
        unshift @$navigation_links,
                $q->a({-href=>"https://$web_server/scgi/server.cgi"},
                      "Current User:$user_name");
    } else {
        unshift @$navigation_links,
                $q->a({-href=>"https://$web_server/scgi/server.cgi"},
                      "Login");
    }
    my $lab_navigation = "<div id=\"navigation_lab\">" .
                         "&bull;&nbsp;" .
                         join("&nbsp;&bull;&nbsp;\n", @$lab_navigation_links) .
                         "&nbsp;&bull;&nbsp;&nbsp;" .
                         "</div>";
    my $navigation = "<div id=\"navigation_second\">" .
                     join("&nbsp;&bull;&nbsp;\n", @$navigation_links) .
                     "</div>";
    return saliweb::server::header($self->{'cgiroot'},
                                   $self->get_header_page_title(),
                                   "none", $projects, $project_menu,
                                   $navigation, $lab_navigation);
}

sub check_optional_email {
    my ($email) = @_;
    if ($email) {
        check_required_email($email);
    }
}

sub check_required_email {
    my ($email) = @_;
    if (!defined($email)
        || $email !~ m/^[\w\.-]+@[\w-]+\.[\w-]+((\.[\w-]+)*)?$/ ) {
        throw saliweb::frontend::InputValidationError(
                 "Please provide a valid return email address");
    }
}

sub check_modeller_key {
    my ($modkey) = @_;
    if (!defined($modkey)) {
        $modkey = '';
    }
    if ($modkey ne "***REMOVED***") {
        throw saliweb::frontend::InputValidationError(
                 "You have entered an invalid MODELLER key: $modkey");
    }
}

sub get_pdb_code {
    my ($code, $outdir) = @_;

    if ($code =~ m/^([A-Za-z0-9]+)$/) {
      $code = lc $1; # PDB codes are case insensitive
    } else {
        throw saliweb::frontend::InputValidationError(
                 "You have entered an invalid PDB code; valid codes " .
                 "contain only letters and numbers, e.g. 1abc");
    }

    my $in_pdb = $pdb_root . substr($code, 1, 2) . "/pdb" . $code . ".ent.gz";
    my $out_pdb = "$outdir/pdb${code}.ent";

    if (! -e $in_pdb) {
        throw saliweb::frontend::InputValidationError(
                 "PDB code '$code' does not exist in our copy of the " .
                 "PDB database.");
    } else {
        system("gunzip -c $in_pdb > $out_pdb") == 0 or
                throw saliweb::frontend::InternalError(
                                 "gunzip of $in_pdb to $out_pdb failed: $?");
        return $out_pdb;
    }
}

# Get chains in PDB file
sub _get_chains_hash_from_pdb {
    my $pdb_file = shift;
    my %chains;
    open FILE, $pdb_file or throw saliweb::frontend::InternalError(
                                      "Cannot open $pdb_file: $!");
    while (my $line = <FILE>) {
       if ($line =~ /^(HETATM|ATOM)/) {
           my $chain = substr($line, 21, 1);
           if ($chain ne ' ') {
               $chains{$chain} = 1;
           }
       }
    }
    close FILE or throw saliweb::frontend::InternalError(
                                      "Cannot close $pdb_file: $!");
    return %chains;
}

# Make a new PDB file containing only the given chains from the input
sub _filter_pdb_chains {
    my ($pdb_file, $out_pdb_file, $chain_ids) = @_;
    open IN, $pdb_file or throw saliweb::frontend::InternalError(
                               "Cannot open $pdb_file: $!");
    open OUT, ">$out_pdb_file" or throw saliweb::frontend::InternalError(
                               "Cannot open $out_pdb_file: $!");
    while (my $line=<IN>) {
       if ($line =~ /^(HETATM|ATOM)/) {
           my $curr_chain_id = substr($line,21,1);
           if ($chain_ids =~ m/$curr_chain_id/) {
               print OUT $line;
           }
       }
    }
    close IN or throw saliweb::frontend::InternalError(
                                      "Cannot close $pdb_file: $!");
    close OUT or throw saliweb::frontend::InternalError(
                                      "Cannot close $out_pdb_file: $!");
}

sub get_pdb_chains {
    my ($pdb_chain, $outdir) = @_;
    my @input = split(':', $pdb_chain);

    my $pdb_file = get_pdb_code($input[0], $outdir);
    if ($#input == 0 or $input[1] eq "-") { # no chains given
        return $pdb_file;
    }

    my $chain_ids = uc $input[1];
    if ($chain_ids !~ /^\w*$/) {
        unlink $pdb_file;
        throw saliweb::frontend::InputValidationError(
                                         "Invalid chain ids $chain_ids");
    }

    # check user-specified chains exist in PDB
    my @user_chains = split(//, $chain_ids);
    my %pdb_chains = _get_chains_hash_from_pdb($pdb_file);
    foreach my $user_chain (@user_chains) {
        if (not exists $pdb_chains{$user_chain}) {
            unlink $pdb_file;
            throw saliweb::frontend::InputValidationError(
                  "The given chain $user_chain does not exist in the PDB file");
        }
    }

    my $out_pdb_file = $outdir . "/" . $input[0] . $chain_ids . ".pdb";
    _filter_pdb_chains($pdb_file, $out_pdb_file, $chain_ids);
    unlink($pdb_file) or throw saliweb::frontend::InternalError(
                        "Cannot unlink $pdb_file: $!");
    return $out_pdb_file;
}

sub check_page_access {
    my ($self, $page_name) = @_;
}

sub format_user_error {
    my ($self, $exc) = @_;
    my $q = $self->{'CGI'};
    my $msg = $exc->text;
    my $ret = $q->h2("Invalid input") .
              $q->p("&nbsp;") .
              $q->p($q->b("An error occurred during your request:")) .
              "<div class=\"standout\"><p>$msg</p></div>";
    if ($exc->isa('saliweb::frontend::InputValidationError')) {
        $ret .= $q->p($q->b("Please click on your browser's \"BACK\" " .
                            "button, and correct the problem."));
    }
    return $ret;
}

sub format_results_error {
    my ($self, $exc) = @_;
    my $q = $self->{'CGI'};
    my $msg = $exc->text;
    return $q->p("$msg.") .
           $q->p("You can check on the status of all jobs at the " .
                 $q->a({-href=>$self->queue_url}, "queue") . " page.");
}

=item get_footer
Return the footer of each web page. By default, this is empty, but it can be
subclassed to display references, contact addresses etc.
=cut
sub get_footer {
    return "";
}

=item get_index_page
Return the HTML content of the index page. This is empty by default, and must
be overridden for each web service. Typically this will display a form for
user input (multi-page input can be supported if intermediate values are
passed between pages).
=cut
sub get_index_page {
    return "";
}

=item get_submit_parameter_help
Return a list of parameters that the submit page will expect, with help for
each. This is used by the REST interface to document the API. Each item in the
list can be the result of parameter() or file_parameter().
=cut
sub get_submit_parameter_help {
    return [];
}

=item parameter
Represent a single parameter (with help), used as input to
get_submit_parameter_help().
=cut
sub parameter {
    my ($self, $key, $help, $optional) = @_;
    $optional = ($optional ? " optional=\"1\"" : "");
    $help =~ s/&/&amp;/g;
    return "      <string name=\"$key\"$optional>$help</string>"
}

=item file_parameter
Represent a single file upload parameter (with help), used as input to
get_submit_parameter_help().
=cut
sub file_parameter {
    my ($self, $key, $help, $optional) = @_;
    $optional = ($optional ? " optional=\"1\"" : "");
    $help =~ s/&/&amp;/g;
    return "      <file name=\"$key\"$optional>$help</file>"
}

=item get_submit_page
Return the HTML content of the submit page (that shown when a job is submitted
to the backend). This is empty by default, and must be overridden for each
web service. Typically this method will perform checks on the input data
(throwing an InputValidationError to report any problems), then call
make_job() and its own submit() method to actually submit the job to the
cluster, then point the user to the URL where job results can be obtained.
=cut
sub get_submit_page {
    return "";
}

=item get_download_page
Return the HTML content of the download page. This is empty by default.
=cut
sub get_download_page {
    return "";
}

=item get_results_page
Return the HTML content of the results page (that shown when the user tries
to view job results). It is passed a CompletedJob object that contains
information such as the name of the job and the time at which job results
will be removed, and is run in the job’s directory. This method is empty
by default, and must be overridden for each web service. Typically this
method will display any job failures (e.g. log files), display the job
results directly, or provide a set of links to allow result files to be
downloaded. In the last case, these URLs are simply the main results URL
with an additional ‘file’ parameter that gives the file name; see
allow_file_download() and get_file_mime_type().
=cut
sub get_results_page {
    return "";
}

=item get_queue_page
Return the HTML content of the queue page. By default this simply shows all
jobs in the queue in date order, plus some basic help text. (Note that there
is currently no interface defined to do this any differently. If you need
to customize the queue page, please talk to Ben so we can design a suitable
interface.)
=cut
sub get_queue_page {
    my $self = shift;
    my $q = $self->{'CGI'};
    my $dbh = $self->{'dbh'};
    my $return = "<h3>Current " . $self->{'server_name'} . " Queue</h3>\n";
    $return .= $q->p($q->a({-href=>'#',
                   -id=>'completedtoggle',
                   -onClick=>"toggle_visibility_tbody('completedjobs', " .
                             "'completedtoggle'); return false;"},
                  "Show completed jobs"));
    # Generate table by hand (not using CGI.pm) since the latter causes
    # "deep recursion" warnings in CGI.pm
    $return .= "<table>\n<thead>\n" .
               "<tr><th>Job ID</th> <th>Submit time (UTC)</th>" .
               "<th>Status</th></tr>\n</thead>\n" .
               "<tbody>\n" .
               join("\n", map { "<tr>$_</tr>" }
                          @{$self->get_queue_rows($q, $dbh, 0)}) .
               "\n</tbody>\n<tbody id='completedjobs' style='display:none'>\n" .
               join("\n", map { "<tr>$_</tr>" }
                          @{$self->get_queue_rows($q, $dbh, 1)}) .
               "\n</tbody>\n</table>\n";

    return $return . $self->get_queue_key();
}

=item get_help_page
Return the HTML content of help, contact, FAQ or news pages; the passed
type parameter will be help, contact, faq, links, about, or news. By default
this simply displays a suitable text file installed as part of the web service
in the txt directory, named help.txt, contact.txt, faq.txt, links.txt,
about.txt, or news.txt respectively.
=cut
sub get_help_page {
    my ($self, $display_type) = @_;
    my $file;
    if ($display_type eq "contact") {
        $file = "contact.txt";
    } elsif ($display_type eq "news") {
        $file = "news.txt";
    } elsif ($display_type eq "faq") {
        $file = "faq.txt";
    } elsif ($display_type eq "links") {
        $file = "links.txt";
    } elsif ($display_type eq "about") {
        $file = "about.txt";
    } else {
        $file = "help.txt";
    }
    return $self->get_text_file($file);
}

sub get_text_file {
    my ($self, $file) = @_;
    open ("TXT","../txt/$file") or return "";
    my $ret = "";
    while ($line=<TXT>) {
        $ret .= $line;
    }
    $ret .= "<div style=\"clear:both;\"></div>";
    return $ret;
}

sub get_queue_rows {
    my ($self, $q, $dbh, $completed) = @_;
    my @rows;
    my $where;
    my $nojobs;
    if ($completed) {
      $where = "state = 'COMPLETED'";
      $nojobs = "No completed jobs";
    } else {
      $where = "state != 'ARCHIVED' and state != 'EXPIRED' and " .
               "state != 'COMPLETED'";
      $nojobs = "No pending or running jobs";
    }
    my $query =
         $dbh->prepare("select * from jobs where $where " .
                       "order by submit_time desc")
             or throw saliweb::frontend::DatabaseError(
                                 "Couldn't prepare query: " . $dbh->errstr);
    $query->execute()
             or throw saliweb::frontend::DatabaseError(
                                 "Couldn't execute query: " . $dbh->errstr);
    my $user = $self->user_name;
    while (my $data = $query->fetchrow_hashref()) {
        # If the job has been submitted to the cluster but hasn't started
        # yet, report it in QUEUED status
        if ($data->{state} eq 'RUNNING') {
            my $state_file = $data->{directory} . '/job-state';
            if (! -f $state_file) {
                $data->{state} = 'QUEUED';
            }
        }
        if ($user && $data->{user} && $data->{user} eq $user) {
            my $jobobj = new saliweb::frontend::CompletedJob($self, $data);
            push @rows, $q->td([$q->a({-href=>$jobobj->results_url},
                                      $data->{name}),
                                $data->{submit_time}, $data->{state}]);
        } else {
            push @rows, $q->td([$data->{name}, $data->{submit_time},
                                $data->{state}]);
        }
    }
    if (!@rows) {
        push @rows, $q->td({-colspan=>3, -class=>'nojobs'}, $nojobs);
    }
    return \@rows;
}

sub get_queue_key {
    my $self = shift;
    my $q = $self->{'CGI'};
    my $maxjobs = $self->{config}->{limits}->{running};
    return
      $q->h3("Key") .
      $q->p($q->a({-href=>'#',
                   -id=>'keytoggle',
                   -onClick=>"toggle_visibility('key', 'keytoggle'); " .
                             "return false;"},
                  "Show")) .
      $q->div({-id=>'key', -style=>'display:none'},
        $q->p($q->b("INCOMING:"),
              " the job has been successfully submitted by the " .
              "web interface, but has not yet started running. " .
              sprintf("No more than %d job%s may run simultaneously on the " .
                      "system.", $maxjobs, ($maxjobs == 1 ? '' : 's'))) .

        $q->p($q->b("QUEUED:"),
              " the job has been passed to our compute cluster, but the " .
              "cluster is currently busy with other jobs, and so the job is " .
              "not yet running. When the system is particularly busy, a job " .
              "could wait for hours or days, so please be patient. " .
              "Resubmitting your job will not help.") .

        $q->p($q->b("RUNNING:"),
              " the job is running on our compute cluster.") .

        $q->p($q->b("COMPLETED:"),
              " the job has finished. You can find the job results " .
              "at the URL given when you submitted it. If you provided an " .
              "email address, you should also receive an email notification " .
              "when the job finishes.") .

        $q->p($q->b("FAILED:"),
              " a technical fault occurred. We are automatically " .
              "notified of such jobs, and will resubmit the job for you once " .
              "the problem has been fixed. (Typically, resubmitting it " .
              "yourself will not help.)")
         );
}

sub _display_content {
    my ($content) = @_;
    print "<div id=\"fullpart\">";
    print $content;
    print "</div></div></div><div style=\"clear:both;\"></div>";
}

sub _display_web_page {
    my ($self, $content) = @_;
    # Call all prefix and suffix methods before printing anything, in case one
    # of them raises an error
    my $prefix = $self->start_html() . $self->get_header();
    my $suffix = $self->get_footer() . "</div>\n" . $self->end_html;
    print $prefix;
    _display_content($content);
    print $suffix;
}

sub display_index_page {
    my $self = shift;
    try {
        $self->check_page_access('index');
        $self->_display_web_page($self->get_index_page());
    } catch saliweb::frontend::UserError with {
        $self->handle_user_error(shift);
    } catch Error with {
        $self->handle_fatal_error(shift);
    };
}

sub _add_incoming_job {
    my ($self, $job) = @_;
    $self->{incoming_jobs}->{$job} = $job;
}

sub _remove_incoming_job {
    my ($self, $job) = @_;
    delete $self->{incoming_jobs}->{$job};
}

sub _add_submitted_job {
    my ($self, $job) = @_;
    push @{$self->{submitted_jobs}}, $job;
}

sub _internal_display_submit_page {
    my ($self, $content, $submitted_jobs) = @_;
    $self->_display_web_page($content);
}

sub display_submit_page {
    my $self = shift;
    $self->{incoming_jobs} = {};
    try {
        my $content;
        $self->set_page_title("Submission");
        try {
            $self->check_page_access('submit');
            $self->{submitted_jobs} = [];
            $content = $self->get_submit_page();
            if (scalar(@{$self->{submitted_jobs}}) == 0) {
                throw saliweb::frontend::InternalError(
                                 "No job submitted by submit page.")
            }
            $self->http_status('201 Created');
            $self->_internal_display_submit_page($content,
                                                 $self->{submitted_jobs});
            delete $self->{submitted_jobs};
        } catch saliweb::frontend::UserError with {
            $self->handle_user_error(shift);
        };
    } catch Error with {
        $self->handle_fatal_error(shift);
    };
    # Clean up any incoming jobs that weren't submitted
    for my $job (values %{$self->{incoming_jobs}}) {
        $job->_cancel();
    }
    delete $self->{incoming_jobs};
}

sub display_queue_page {
    my $self = shift;
    try {
        $self->set_page_title("Queue");
        $self->check_page_access('queue');
        $self->_display_web_page($self->get_queue_page());
    } catch saliweb::frontend::UserError with {
        $self->handle_user_error(shift);
    } catch Error with {
        $self->handle_fatal_error(shift);
    };
}

sub display_download_page {
    my $self = shift;
    try {
        $self->set_page_title("Download");
        $self->check_page_access('download');
        $self->_display_web_page($self->get_download_page());
    } catch saliweb::frontend::UserError with {
        $self->handle_user_error(shift);
    } catch Error with {
        $self->handle_fatal_error(shift);
    };
}

sub display_help_page {
    my $self = shift;
    try {
        my $q = $self->{'CGI'};
        my $display_type = $q->param('type') || 'help';
        my $style = $q->param('style') || '';
        $self->set_page_title("Help");
        $self->check_page_access('help');
        my $content = $self->get_help_page($display_type);
        if ($style eq "helplink") {
            print $self->start_html("/saliweb/css/help.css");
            print "<div><div>";
            _display_content($content);
            print $self->end_html;
        } else {
            $self->_display_web_page($content);
        }
    } catch saliweb::frontend::UserError with {
        $self->handle_user_error(shift);
    } catch Error with {
        $self->handle_fatal_error(shift);
    };
}

sub display_results_page {
    my $self = shift;
    try {
        $self->set_page_title("Results");
        $self->check_page_access('results');
        $self->_internal_display_results_page();
    } catch saliweb::frontend::UserError with {
        $self->handle_user_error(shift);
    } catch saliweb::frontend::ResultsError with {
        my $exc = shift;
        $self->http_status($exc->http_status);
        my $content = $self->format_results_error($exc);
        $self->_display_web_page($content);
    } catch Error with {
        $self->handle_fatal_error(shift);
    };
}
 
sub _internal_display_results_page {
    my $self = shift;
    my $q = $self->{'CGI'};
    my $dbh = $self->{'dbh'};

    my $job;
    my $file;
    if ($q->path_info =~ m#^/+([^/]+)/*$#) {
        $job = $1;
    } elsif ($q->path_info =~ m#^/+([^/]+)/+(.+)$#) {
        $job = $1;
        $file = $2;
    }

    my $passwd = $q->param('passwd');

    if (!defined($job) || !defined($passwd)) {
        throw saliweb::frontend::ResultsBadURLError(
                       "Missing job name and password");
    }

    my $query = $dbh->prepare("select * from jobs where name=? and passwd=?")
             or throw saliweb::frontend::DatabaseError(
                                 "Couldn't prepare query: " . $dbh->errstr);
    $query->execute($job, $passwd)
             or throw saliweb::frontend::DatabaseError(
                                 "Couldn't execute query: " . $dbh->errstr);

    my $job_row = $query->fetchrow_hashref();

    if (!$job_row) {
        throw saliweb::frontend::ResultsBadJobError(
                 "Job does not exist, or wrong password");
    } elsif ($job_row->{state} eq 'EXPIRED'
             || $job_row->{state} eq 'ARCHIVED') {
        throw saliweb::frontend::ResultsGoneError(
                 "Results for job '$job' are no longer available " .
                 "for download");
    } elsif ($job_row->{state} ne 'COMPLETED') {
        throw saliweb::frontend::ResultsStillRunningError(
                 "Job '$job' has not yet completed; please check " .
                 "back later");
    } else {
        chdir($job_row->{directory});
        if (defined($file)) {
            if (-f $file and $file !~ /^\s*\// and $file !~ /\.\./
                and $self->allow_file_download($file)) {
                $self->download_file($q, $file);
            } else {
                throw saliweb::frontend::ResultsBadFileError(
                           "Invalid results file requested");
            }
        } else {
            my $jobobj = new saliweb::frontend::CompletedJob($self, $job_row);
            my $contents = $self->get_results_page($jobobj);
            $self->_display_results_page_index($contents, $jobobj);
        }
    }
}

sub _display_results_page_index {
    my ($self, $contents, $jobobj) = @_;
    $self->_display_web_page($contents);
}

=item allow_file_download
When downloading a results file (see get_results_page()) this method is
called to check whether the file is allowed to be downloaded, and should
return true if it is. (For example, the job results directory may contain
intermediate output files that should not be downloaded for efficiency or
security reasons.) By default, this method always returns true.
=cut
sub allow_file_download {
    my ($self, $file) = @_;
    return 1;
}

sub get_file_mime_type {
    return 'text/plain';
}

sub download_file {
    my ($self, $q, $file) = @_;
    open(FILE, "$file")
        or throw saliweb::frontend::InternalError("Cannot open $file: $!");
    print $q->header($self->get_file_mime_type($file));
    while(<FILE>) {
        print;
    }
    close FILE;
}

sub help_link {
    my ($self, $target) = @_;

    my $q = $self->{'CGI'};
    my $url=$self->help_url."&style=helplink#$target";

    return $q->a({-href=>"$url",
                  -class=>"helplink",
                  -onClick=>"launchHelp(\'$url\'); return false;"},
                 $q->img({-src=>"/saliweb/img/help.jpg", -alt=>"help",
                          -class=>"helplink"} ));
}

sub make_job {
  my ($self, $user_jobname, $email) = @_;
  # Note that the email argument is deprecated (should be passed in submit()
  # instead) since it will be forgotten by resumed jobs
  return new saliweb::frontend::IncomingJob($self, $user_jobname, $email);
}

sub resume_job {
  my ($self, $jobname) = @_;
  return resume saliweb::frontend::IncomingJob($self, $jobname);
}

sub read_ini_file {
  my ($filename) = @_;
  open(FILE, $filename)
        or throw saliweb::frontend::InternalError("Cannot open $filename: $!");
  my $contents;
  my $section;
  # Set defaults
  $contents->{limits}->{running} = 5;
  while(<FILE>) {
    if (/^\[(\S+)\]$/) {
      $section = lc $1;
    } elsif (/^\s*(\S+?)\s*[=:]\s*(\S+)\s*$/) {
      my $key = lc $1;
      my $value = $2;
      if ($section eq 'directories' and $key ne 'install') {
        $key = uc $key;
      }
      $contents->{$section}->{$key} = $value;
    }
  }
  close FILE;
  return $contents;
}

sub read_config {
  my ($filename, $frontend) = @_;
  my $contents = read_ini_file($filename);
  if (defined($frontend)) {
    # Overwrite variables with those of the alternative frontend selected
    my $sec = "frontend:$frontend";
    $contents->{general}->{urltop} = $contents->{$sec}->{urltop};
  }
  my ($vol, $dirs, $file) = File::Spec->splitpath($filename);
  my $frontend_file = File::Spec->rel2abs(
                             $contents->{database}->{frontend_config}, $dirs);
  my $frontend_config = read_ini_file($frontend_file);
  $contents->{database}->{user} = $frontend_config->{frontend_db}->{user};
  $contents->{database}->{passwd} = $frontend_config->{frontend_db}->{passwd};
  return $contents;
}

sub connect_to_database {
  my ($config) = @_;
  my $dbh = DBI->connect("DBI:mysql:" . $config->{database}->{db},
                         $config->{database}->{user},
                         $config->{database}->{passwd})
            or throw saliweb::frontend::DatabaseError(
                       "Cannot connect to database: $!");
  return $dbh;
}

1;

package saliweb::frontend::UserError;
use base qw(Error::Simple);
1;

package saliweb::frontend::InputValidationError;
our @ISA = 'saliweb::frontend::UserError';

sub http_status {
    return "400 Bad Request";
}
1;

package saliweb::frontend::AccessDeniedError;
our @ISA = 'saliweb::frontend::UserError';

sub http_status {
    return "401 Unauthorized";
}
1;

package saliweb::frontend::InternalError;
use base qw(Error::Simple);
1;

package saliweb::frontend::DatabaseError;
use base qw(Error::Simple);
1;

package saliweb::frontend::ResultsError;
use base qw(Error::Simple);
1;

package saliweb::frontend::ResultsBadURLError;
our @ISA = 'saliweb::frontend::ResultsError';

sub http_status {
    return '400 Bad Request';
}
1;

package saliweb::frontend::ResultsBadJobError;
our @ISA = 'saliweb::frontend::ResultsError';

sub http_status {
    return '400 Bad Request';
}
1;

package saliweb::frontend::ResultsBadFileError;
our @ISA = 'saliweb::frontend::ResultsError';

sub http_status {
    return '404 Not Found';
}
1;

package saliweb::frontend::ResultsGoneError;
our @ISA = 'saliweb::frontend::ResultsError';

sub http_status {
    return "410 Gone";
}
1;

package saliweb::frontend::ResultsStillRunningError;
our @ISA = 'saliweb::frontend::ResultsError';

sub http_status {
    return "503 Service Unavailable";
}
1;
