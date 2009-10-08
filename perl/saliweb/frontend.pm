package IncomingJob;

use IO::Socket;

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
  my $query = "insert into jobs (name,passwd,contact_email,directory,url," .
              "submit_time) VALUES(?, ?, ?, ?, ?, UTC_TIMESTAMP())";
  my $in = $dbh->prepare($query) or die "Cannot prepare query ". $dbh->errstr;
  $in->execute($self->{name}, $self->{passwd}, $self->{email},
               $self->{directory}, $self->{url})
        or die "Cannot execute query " . $dbh->errstr;

  # Use socket to inform backend of new incoming job
  my $s = IO::Socket::UNIX->new(Peer=>$config->{general}->{'socket'},
                                Type=>SOCK_STREAM);
  if (defined($s)) {
    print $s "INCOMING " . $self->{name};
    $s->close();
  }
}

sub _get_job_name_directory {
  my ($frontend, $user_jobname) = @_;
  my $config = $frontend->{'config'};
  my $dbh = $frontend->{'dbh'};
  # Remove potentially dodgy characters in jobname
  $user_jobname =~ s/[^a-zA-Z0-9_-]//g;
  # Make sure jobname fits in the db (plus extra space for
  # auto-generated suffix if needed)
  $user_jobname = substr($user_jobname, 0, 30);

  my $query = $dbh->prepare('select count(name) from jobs where name=?')
                 or die "Cannot prepare query ". $dbh->errstr;
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
  die "Could not determine a unique job name";
}

sub _generate_results_url {
    my ($frontend, $jobname) = @_;
    my $passwd = &generate_random_passwd(10);
    $url = $frontend->cgiroot . "/results.cgi?job=$jobname&passwd=$passwd";
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
  $query->execute($jobname) or die "Cannot execute: " . $dbh->errstr;
  my @data = $query->fetchrow_array();
  if ($data[0] == 0) {
    mkdir($jobdir) or die "Cannot make job directory $jobdir: $!";
    $query->execute($jobname) or die "Cannot execute: " . $dbh->errstr;
    @data = $query->fetchrow_array();
    if ($data[0] == 0) {
      return $jobdir;
    }
  }
}

package CompletedJob;

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
        die "Cannot parse time $db_utc_time";
    }
}


package saliweb::frontend;

use saliweb::server qw(validate_user);

require Exporter;
@ISA = qw(Exporter);
@EXPORT = qw(check_optional_email check_required_email);

use File::Spec;
use DBI;
use CGI;
use Error qw(:try);

our $web_server = 'modbase.compbio.ucsf.edu';

sub new {
    my ($invocant, $config_file, $server_name) = @_;
    my $class = ref($invocant) || $invocant;
    my $self = {};
    bless($self, $class);
    $self->{'CGI'} = $self->_setup_cgi();
    $self->{'server_name'} = $server_name;
    # Read configuration file
    $self->{'config'} = my $config = read_config($config_file);
    $self->{'htmlroot'} = $config->{general}->{urltop} . "/html/";
    $self->{'cgiroot'} = $config->{general}->{urltop};
    $self->{'dbh'} = my $dbh = connect_to_database($config);
    $self->_setup_user($dbh);
    return $self;
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

sub email {
    my $self = shift;
    if (defined($self->{'user_info'})) {
        return $self->{'user_info'}->{'email'};
    }
}

sub _setup_cgi {
    return new CGI;
}

sub _setup_user {
    my ($self, $dbh) = @_;
    my $q = $self->{'CGI'};

    my %cookie = $q->cookie('sali-servers');
    $self->{'user_name'} = "Anonymous";
    $self->{'user_info'} = undef;
    if ($cookie{'user_name'}) {
        my ($user_name, $hash, $user_info) =
            &validate_user($dbh, 'servers', 'hash', $cookie{'user_name'},
                           $cookie{'session'});
        if (($user_name ne "not validated") && ($user_name ne "")
            && ($user_name)) {
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
           $q->start_html(-title => $self->{'server_name'},
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
    my $project_menu = $self->get_project_menu($q);
    my $navigation_links = $self->get_navigation_links($q);
    my $user_name = $self->{'user_name'};
    unshift @$navigation_links,
            $q->a({-href=>"https://$web_server/scgi/server.cgi?logout=true"},
                  "Logout");
    unshift @$navigation_links,
            $q->a({-href=>"https://$web_server/scgi/server.cgi"},
                  "Current User:$user_name");
    my $navigation = "<div id=\"navigation_second\">" .
                     join("&nbsp;&bull;&nbsp;\n", @$navigation_links) .
                     "</div>";
    return saliweb::server::header($self->{'cgiroot'}, $self->{'server_name'},
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
    if ($email !~ m/^[\w\.-]+@[\w-]+\.[\w-]+((\.[\w-]+)*)?$/ ) {
        throw saliweb::frontend::InputValidationError(
                 "Please provide a valid return email address");
    }
}

sub failure {
    my ($self, $msg) = @_;
    my $q = $self->{'CGI'};
    return $q->table(
               $q->Tr($q->td({-class=>"redtxt", -align=>"left"},
                      $q->h3("Server Error:"))) .
               $q->Tr($q->td($q->b("An error occured during your request:"))) .
               $q->Tr($q->td("<div class=standout>$msg</div>")) .
               $q->Tr($q->td($q->b("Please click on your browser's \"BACK\" " .
                                   "button, and correct " .
                                   "the problem.",$q->br))));
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
    open ("TXT","../txt/$file");
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
              or die "Couldn't prepare query " . $dbh->errstr;
    $query->execute() or die "Couldn't execute query " . $dbh->errstr;
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
    print $self->start_html();
    print $self->header();
    _display_content($content);
    print $self->footer();
    print "</div>\n";
    print $self->end_html;
}

sub display_index_page {
    my $self = shift;
    $self->_display_web_page($self->get_index_page());
}

sub display_submit_page {
    my $self = shift;
    my $content;
    try {
        $content = $self->get_submit_page();
    } catch saliweb::frontend::InputValidationError with {
        my $ex = shift;
        $content = $self->failure($ex->text);
    };
    $self->_display_web_page($content);
}

sub display_queue_page {
    my $self = shift;
    $self->_display_web_page($self->get_queue_page());
}

sub display_help_page {
    my $self = shift;
    my $q = $self->{'CGI'};
    my $display_type = $q->param('type') || 'help';
    my $style = $q->param('style') || '';
    my $content = $self->get_help_page($display_type);
    if ($style eq "helplink") {
        print $self->start_html("/saliweb/css/help.css");
        _display_content($content);
        print $self->end_html;
    } else {
        $self->_display_web_page($content);
    }
}

sub display_results_page {
    my $self = shift;
    my $q = $self->{'CGI'};
    my $dbh = $self->{'dbh'};

    my $job = $q->param('job');
    my $passwd = $q->param('passwd');
    my $file = $q->param('file');

    if (!defined($job) || !defined($passwd)) {
        $self->_display_web_page(
                 $q->p("Missing 'job' and 'passwd' parameters."));
        return;
    }

    my $query = $dbh->prepare("select * from jobs where name=? and passwd=?")
                or die "Cannot prepare: " . $dbh->errstr;
    $query->execute($job, $passwd) or die "Cannot execute " . $dbh->errstr;

    my $job_row = $query->fetchrow_hashref();

    if (!$job_row) {
        $self->_display_web_page(
                 $q->p("Job '$job' does not exist, or wrong password."));
    } elsif ($job_row->{state} ne 'COMPLETED') {
        $self->_display_web_page(
                 $q->p("Job '$job' has not yet completed; please check " .
                       "back later.") .
                 $q->p("You can also check on your job at the " .
                       "<a href=\"queue\">queue</a> page."));
    } else {
        chdir($job_row->{directory});
        if (defined($file) and -f $file and $self->allow_file_download($file)) {
            $self->download_file($q, $file);
        } else {
            my $jobobj = new CompletedJob($job_row);
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
    print $q->header($self->get_file_mime_type($file));
    open(FILE, "$file") or die "Cannot open $file: $!";
    while(<FILE>) {
        print;
    }
    close FILE;
}

sub help_link {
    my ($self, $target) = @_;

    my $q = $self->{'CGI'};
    my $url = "help.cgi?style=helplink&type=help#$target";

    return $q->a({-href=>"$url",-border=>"0",
                  -onClick=>"launchHelp(\'$url\'); return false;"},
                 $q->img({-src=>"/saliweb/img/help.jpg", -border=>0,
                          -valign=>"bottom", -alt=>"help"} ));
}

sub make_job {
  my ($self, $user_jobname, $email) = @_;
  return new IncomingJob($self, $user_jobname, $email);
}

sub read_ini_file {
  my ($filename) = @_;
  open(FILE, $filename) or die "Cannot open $filename: $!";
  my $contents;
  my $section;
  while(<FILE>) {
    if (/^\[(\S+)\]$/) {
      $section = lc $1;
    } elsif (/^\s*(\S+)\s*[=:]\s*(\S+)\s*$/) {
      my ($key, $value) = (lc $1, $2);
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
            or die "Cannot connect to database: $!";
  return $dbh;
}

1;

package saliweb::frontend::InputValidationError;
use base qw(Error::Simple);
1;
