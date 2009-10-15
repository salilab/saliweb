package saliweb::frontend::IncomingJob;

use IO::Socket;
use Fcntl ':flock';

sub new {
    my ($invocant, $frontend, $given_name, $email) = @_;
    my $class = ref($invocant) || $invocant;
    my $self = {};
    bless($self, $class);
    $self->{frontend} = $frontend;
    $self->{given_name} = $given_name;
    $self->{email} = $email;
    ($self->{name}, $self->{directory}) = _get_job_name_directory($frontend,
                                                                  $given_name);
    ($self->{url}, $self->{passwd}) = _generate_results_url($frontend,
                                                            $self->{name});
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
    return $self->{url};
}

sub submit {
  my $self = shift;
  my $config = $self->{frontend}->{'config'};
  my $dbh = $self->{frontend}->{'dbh'};

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
}

sub _sanitize_jobname {
    my $jobname = shift;
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
    $url = $frontend->cgiroot . "/results.cgi?job=$jobname&amp;passwd=$passwd";
    return ($url, $passwd);
}

sub generate_random_passwd {
  # Generate a random alphanumeric password of the given length
  my ($len) = @_;
  my @validchars = ('a'..'z', 'A'..'Z', 0..9);
  my $randstr = join '', map $validchars[rand @validchars], 1..$len;
  return $randstr;
}

sub try_job_name {
  my ($jobname, $query, $dbh, $config) = @_;
  my $jobdir = $config->{directories}->{INCOMING} . "/" . $jobname;
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
    my ($invocant, $job_row) = @_;
    my $class = ref($invocant) || $invocant;
    my %hash = %$job_row;
    my $self = \%hash;
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
    my ($self, $q) = @_;
    if ($self->unix_archive_time) {
        return $q->p("Job results will be available at this URL for " .
                     $self->to_archive_time . ".");
    } else {
        return "";
    }
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
@EXPORT = qw(check_optional_email check_required_email check_modeller_key);

use File::Spec;
use DBI;
use CGI;
use Error qw(:try);
use MIME::Lite;
use Fcntl ':flock';

our $web_server = 'modbase.compbio.ucsf.edu';

sub new {
    my ($invocant, $config_file, $version, $server_name) = @_;
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
        $self->{'config'} = my $config = read_config($config_file);
        my $urltop = $config->{general}->{urltop};
        # Make sure any links we generate are also secure if we are secure
        if ($self->cgi->https) {
            $urltop =~ s/^http:/https:/;
        }
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

sub handle_fatal_error {
    my ($self, $exc) = @_;
    my $q = new CGI; # We may not have created $self->cgi yet
    my $status = "500 Internal Server Error";
    print $q->header(-status=>$status) .
          $q->start_html(-title => $status) .
          $q->h1($status) .
          $q->p("A fatal internal error occurred in this web service. ". 
                "We have been notified of the problem, and should " .
                "fix it shortly.") .
          $q->p("For your reference, the error message reported is below:") .
          $q->pre($exc) .
          $q->p("Apologies for the inconvenience.") .
          $q->end_html;

    $self->_email_admin_fatal_error($exc);

    # Rethrow the error to terminate the process
    $exc->throw();
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

sub cgi {
    my $self = shift;
    return $self->{CGI};
}

sub version {
    my $self = shift;
    return $self->{version};
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
    return ".";
}

sub submit_url {
    return "submit.cgi";
}

sub queue_url {
    return "queue.cgi";
}

sub help_url {
    return "help.cgi?type=help";
}

sub news_url {
    return "help.cgi?type=news";
}

sub contact_url {
    return "help.cgi?type=contact";
}

sub results_url {
    return "results.cgi";
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
    return $q->header .
           $q->start_html(-title => $self->{page_title},
                          -style => {-src=>$style},
                          -onload=>"opt.init(document.forms[0])",
                          -script=>[{-language => 'JavaScript',
                                     -src=>"/saliweb/js/salilab.js"}]
                          );
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

sub get_project_menu {
    return "";
}

sub get_navigation_links {
    return [];
}

sub header {
    my $self = shift;
    my $q = $self->{'CGI'};
    my $projects = $self->get_projects();
    my $project_menu = $self->get_project_menu();
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
    my $navigation = "<div id=\"navigation_second\">" .
                     join("&nbsp;&bull;&nbsp;\n", @$navigation_links) .
                     "</div>";
    return saliweb::server::header($self->{'cgiroot'}, $self->{page_title},
                                   "none", $projects, $project_menu,
                                   $navigation);
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
    if (!defined($modkey) || $modkey ne "***REMOVED***") {
        throw saliweb::frontend::InputValidationError(
                 "You have entered an invalid MODELLER key");
    }
}

sub format_input_validation_error {
    my ($self, $exc) = @_;
    my $q = $self->{'CGI'};
    my $msg = $exc->text;
    return $q->h2("Invalid input") .
           $q->p("&nbsp;") .
           $q->p($q->b("An error occurred during your request:")) .
           "<div class=\"standout\"><p>$msg</p></div>" .
           $q->p($q->b("Please click on your browser's \"BACK\" " .
                       "button, and correct the problem."));
}


sub footer {
    return "";
}

sub get_index_page {
    return "";
}

sub get_submit_page {
    return "";
}

sub get_results_page {
    return "";
}

sub get_queue_page {
    my $self = shift;
    my $q = $self->{'CGI'};
    my $dbh = $self->{'dbh'};
    my $return = "<h3>Current " . $self->{'server_name'} . " Queue</h3>\n";
    $return .= $q->table($q->Tr([$q->th(['Job ID', 'Submit time (UTC)',
                                         'Status']),
                                 $self->get_queue_rows($q, $dbh)
                                ]));

    return $return . $self->get_queue_key();
}

sub get_help_page {
    my ($self, $display_type) = @_;
    my $file;
    if ($display_type eq "contact") {
        $file = "contact.txt";
    } elsif ($display_type eq "news") {
        $file = "news.txt";
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
    my ($self, $q, $dbh) = @_;
    my @rows;
    my $query =
         $dbh->prepare("select name,submit_time,state from jobs " .
                       "where state != 'ARCHIVED' and state != 'EXPIRED' ".
                       "order by submit_time desc")
             or throw saliweb::frontend::DatabaseError(
                                 "Couldn't prepare query: " . $dbh->errstr);
    $query->execute()
             or throw saliweb::frontend::DatabaseError(
                                 "Couldn't execute query: " . $dbh->errstr);
    while (my @data = $query->fetchrow_array()) {
        push @rows, $q->td([$data[0], $data[1], $data[2]]);
    }
    return @rows;
}

sub get_queue_key {
    my $self = shift;
    my $q = $self->{'CGI'};
    return
      $q->h3("Key") .
      $q->p($q->b("INCOMING:"),
            " the job has been successfully submitted by the " .
            "web interface. If your job is stuck in this state for more than " .
            "15 minutes, contact us for help.") .

      $q->p($q->b("RUNNING:"),
            " the job is running on our grid machines. When the system is " .
            "is particularly busy, this could take hours or days, so please " .
            "be patient. Resubmitting your job will not help.") .

      $q->p($q->b("COMPLETED:"),
            " the job has finished. You can find the job " .
            "results at the URL given when you submitted it. If you provided " .
            "an email address, you should also receive an email notification " .
            "when the job finishes.") .

      $q->p($q->b("FAILED:"),
            " a technical fault occurred. We are automatically " .
            "notified of such jobs, and will resubmit the job for you once " .
            "the problem has been fixed. (Typically, resubmitting it " .
            "yourself will not help.)");
}

sub _display_content {
    my ($content) = @_;
    print "<div id=\"fullpart\">";
    print $content;
    print "</div></div><div style=\"clear:both;\"></div>";
}

sub _display_web_page {
    my ($self, $content) = @_;
    # Call all prefix and suffix methods before printing anything, in case one
    # of them raises an error
    my $prefix = $self->start_html() . $self->header();
    my $suffix = $self->footer() . "</div>\n" . $self->end_html;
    print $prefix;
    _display_content($content);
    print $suffix;
}

sub display_index_page {
    my $self = shift;
    try {
        $self->_display_web_page($self->get_index_page());
    } catch Error with {
        $self->handle_fatal_error(shift);
    };
}

sub display_submit_page {
    my $self = shift;
    try {
        my $content;
        $self->set_page_title("Submission");
        try {
            $content = $self->get_submit_page();
        } catch saliweb::frontend::InputValidationError with {
            $content = $self->format_input_validation_error(shift);
        };
        $self->_display_web_page($content);
    } catch Error with {
        $self->handle_fatal_error(shift);
    };
}

sub display_queue_page {
    my $self = shift;
    try {
        $self->set_page_title("Queue");
        $self->_display_web_page($self->get_queue_page());
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
        my $content = $self->get_help_page($display_type);
        if ($style eq "helplink") {
            print $self->start_html("/saliweb/css/help.css");
            _display_content($content);
            print $self->end_html;
        } else {
            $self->_display_web_page($content);
        }
    } catch Error with {
        $self->handle_fatal_error(shift);
    };
}

sub display_results_page {
    my $self = shift;
    try {
        $self->_internal_display_results_page();
    } catch Error with {
        $self->handle_fatal_error(shift);
    };
}
 
sub _internal_display_results_page {
    my $self = shift;
    my $q = $self->{'CGI'};
    my $dbh = $self->{'dbh'};

    my $job = $q->param('job');
    my $passwd = $q->param('passwd');
    my $file = $q->param('file');
    $self->set_page_title("Results");

    if (!defined($job) || !defined($passwd)) {
        $self->_display_web_page(
                 $q->p("Missing 'job' and 'passwd' parameters."));
        return;
    }

    my $query = $dbh->prepare("select * from jobs where name=? and passwd=?")
             or throw saliweb::frontend::DatabaseError(
                                 "Couldn't prepare query: " . $dbh->errstr);
    $query->execute($job, $passwd)
             or throw saliweb::frontend::DatabaseError(
                                 "Couldn't execute query: " . $dbh->errstr);

    my $job_row = $query->fetchrow_hashref();

    if (!$job_row) {
        $self->_display_web_page(
                 $q->p("Job '$job' does not exist, or wrong password."));
    } elsif ($job_row->{state} ne 'COMPLETED') {
        $self->_display_web_page(
                 $q->p("Job '$job' has not yet completed; please check " .
                       "back later.") .
                 $q->p("You can also check on your job at the " .
                       $q->a({-href=>$self->queue_url}, "queue") . " page."));
    } else {
        chdir($job_row->{directory});
        if (defined($file)) {
            if (-f $file and $file !~ /^\s*\// and $file !~ /\.\./
                and $self->allow_file_download($file)) {
                $self->download_file($q, $file);
            } else {
                $self->_display_web_page(
                     $q->p("Invalid results file requested"));
            }
        } else {
            my $jobobj = new saliweb::frontend::CompletedJob($job_row);
            $self->_display_web_page($self->get_results_page($jobobj));
        }
    }
}

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
    my $url = "help.cgi?style=helplink&type=help#$target";

    return $q->a({-href=>"$url",
                  -class=>"helplink",
                  -onClick=>"launchHelp(\'$url\'); return false;"},
                 $q->img({-src=>"/saliweb/img/help.jpg", -alt=>"help",
                          -class=>"helplink"} ));
}

sub make_job {
  my ($self, $user_jobname, $email) = @_;
  return new saliweb::frontend::IncomingJob($self, $user_jobname, $email);
}

sub read_ini_file {
  my ($filename) = @_;
  open(FILE, $filename)
        or throw saliweb::frontend::InternalError("Cannot open $filename: $!");
  my $contents;
  my $section;
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
  my ($filename) = @_;
  my $contents = read_ini_file($filename);
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

package saliweb::frontend::InputValidationError;
use base qw(Error::Simple);
1;

package saliweb::frontend::InternalError;
use base qw(Error::Simple);
1;

package saliweb::frontend::DatabaseError;
use base qw(Error::Simple);
1;
