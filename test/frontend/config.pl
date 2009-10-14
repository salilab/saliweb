#!/usr/bin/perl -w

use lib '.';
use test_setup;

use Test::More 'no_plan';
use Test::Exception;
use Error;
use File::Temp qw(tempdir);
use strict;

BEGIN { use_ok('saliweb::frontend'); }

# Test reading in .ini files
{
    throws_ok { saliweb::frontend::read_ini_file("/not/exist.ini") }
              'saliweb::frontend::InternalError',
              "read_ini_file should fail on files that don't exist";
    like($@, qr#Cannot open /not/exist\.ini#, '... check exception message');

    my $fh = File::Temp->new();
    print $fh <<END;
[SectionTitle]
key1: value1
Key2 = VALUE2
[directories]
install= installvalue
incoming=incomingvalue
running=runningvalue
END
    $fh->close() or die "Cannot close temporary file: $!";

    my $config = saliweb::frontend::read_ini_file($fh->filename);
    ok($config->{sectiontitle}, "ini file section titles are lowercased");
    is($config->{sectiontitle}->{key1}, 'value1',
       'key:value, whitespace stripped');
    is($config->{sectiontitle}->{key2}, 'VALUE2',
       'key=value, case preserved in values but not keys');
    is($config->{directories}->{install}, 'installvalue',
       '{directories}->{install} key should be lowercase');
    is($config->{directories}->{INCOMING}, 'incomingvalue',
       'directory key for job state INCOMING should be caps');
    is($config->{directories}->{RUNNING}, 'runningvalue',
       'directory key for job state RUNNING should be caps');
}

# Test read_config function
{
    my $dir = tempdir( CLEANUP => 1 );
    my $main = "$dir/main.ini";
    my $frontend = "$dir/frontend.ini";

    open(FH, "> $main") or die "Cannot open $main: $!";
    # Note that path to frontend.ini is relative to that of main.ini
    print FH <<END;
[database]
frontend_config=frontend.ini
END
    close FH or die "Cannot close $main: $!";

    open(FH, "> $frontend") or die "Cannot open $frontend: $!";
    print FH <<END;
[frontend_db]
user=myuser
passwd=mypasswd
END
    close FH or die "Cannot close $frontend: $!";

    my $config = saliweb::frontend::read_config($main);
    is($config->{database}->{frontend_config}, 'frontend.ini',
       'check read of config file frontend_config key');
    is($config->{database}->{user}, 'myuser',
       'check read of config file database user key');
    is($config->{database}->{passwd}, 'mypasswd',
       'check read of config file database password key');
}
