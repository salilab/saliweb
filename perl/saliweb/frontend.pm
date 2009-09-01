package saliweb::frontend;
require Exporter;
@ISA = qw(Exporter);
@EXPORT = qw(read_config connect_to_database);

use File::Spec;
use DBI;

sub read_ini_file {
  # Read an ini file that contains variable assignments (either key=value or
  # key: value) within named sections (e.g. [section])
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
  # Read in the web service configuration file, including the frontend
  # database username and password
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
  # Connect to the MySQL database, using the information contained
  # in the configuration.
  my ($config) = @_;
  my $dbh = DBI->connect("DBI:mysql:" . $config->{database}->{db},
                         $config->{database}->{user},
                         $config->{database}->{passwd})
            or die "Cannot connect to database: $!";
  return $dbh;
}

1;
