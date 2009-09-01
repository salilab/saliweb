package saliweb::frontend;
require Exporter;
@ISA = qw(Exporter);
@EXPORT = qw(read_config connect_to_database make_job);

use File::Spec;
use DBI;

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

1;
