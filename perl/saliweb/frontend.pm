package saliweb::frontend;
use saliweb::server;
require Exporter;
@ISA = qw(Exporter);
@EXPORT = qw(read_config connect_to_database make_job submit_job
             generate_random_passwd);

use File::Spec;
use IO::Socket;
use DBI;
use CGI;

sub new {
    my ($invocant, $config_file, $server_name) = @_;
    my $class = ref($invocant) || $invocant;
    my $self = {};
    bless($self, $class);
    $self->{'CGI'} = $self->_setup_cgi();
    $self->{'server_name'} = $server_name;
    # Read configuration file
    $self->{'config'} = my $config = read_config($config_file);
    $self->{'htmlroot'} = $config->{general}->{urltop};
    $self->{'cgiroot'} = $self->{'htmlroot'} . "/cgi/";
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
    my ($self) = @_;
    my $q = $self->{'CGI'};
    my $style = "/saliweb/css/server.css";
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

sub header {
    my $self = shift;
    my $q = $self->{'CGI'};
    my $projects = $self->get_projects();
    my $project_menu = $self->get_project_menu($q);
    my $navigation_links = $self->get_navigation_links($q);
    my $user_name = $self->{'user_name'};
    unshift @$navigation_links,
            $q->a({-href=>"/scgi/server.cgi?logout=true"},"Logout");
    unshift @$navigation_links,
            $q->a({-href=>"/scgi/server.cgi"},"Current User:$user_name");
    my $navigation = "<div id=\"navigation_second\">" .
                     join("&nbsp;&bull;&nbsp;\n", @$navigation_links) .
                     "</div>";
    return saliweb::server::header($self->{'cgiroot'}, $self->{'server_name'},
                                   "none", $projects, $project_menu,
                                   $navigation);
}

sub footer {
    return "";
}

sub get_index_page {
    return "not implemented";
}

sub display_index_page {
    my ($self) = @_;
    print $self->start_html();
    print $self->header();
    print "<div id=\"fullpart\">";
    print $self->get_index_page();
    print "</div></div><div style=\"clear:both;\"></div>";
    print $self->footer();
    print $self->end_html;
}

sub help_link {
    my ($self, $target);
    my $self = shift;
    return saliweb::server::help_link($self->{'server_name'}, $target);
}

# Old non-OO stuff

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

sub make_job {
  my ($config, $dbh, $user_jobname) = @_;
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

sub submit_job {
  my ($config, $dbh, $jobname, $passwd, $email, $jobdir, $url) = @_;

  # Insert row into database table
  my $query = "insert into jobs (name,passwd,contact_email,directory,url," .
              "submit_time) VALUES(?, ?, ?, ?, ?, UTC_TIMESTAMP())";
  my $in = $dbh->prepare($query) or die "Cannot prepare query ". $dbh->errstr;
  $in->execute($jobname, $passwd, $email, $jobdir, $url)
        or die "Cannot execute query " . $dbh->errstr;

  # Use socket to inform backend of new incoming job
  my $s = IO::Socket::UNIX->new(Peer=>$config->{general}->{'socket'},
                                Type=>SOCK_STREAM);
  if (defined($s)) {
    print $s "INCOMING $jobname";
    $s->close();
  }
}

sub generate_random_passwd {
  # Generate a random alphanumeric password of the given length
  my ($len) = @_;
  my @validchars = ('a'..'z', 'A'..'Z', 0..9);
  my $randstr = join '', map $validchars[rand @validchars], 1..$len;
  return $randstr;
}

1;
