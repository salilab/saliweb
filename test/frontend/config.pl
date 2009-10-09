#!/usr/bin/perl -w

use lib '.';
use test_setup;

use Test::More 'no_plan';
use Test::Exception;
use Error;
use File::Temp;

BEGIN { use_ok('saliweb::frontend'); }

# Test reading in .ini files
{
    throws_ok { saliweb::frontend::read_ini_file("/not/exist.ini") }
              saliweb::frontend::InternalError,
              "read_ini_file should fail on files that don't exist";

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
