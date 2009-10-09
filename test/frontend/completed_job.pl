#!/usr/bin/perl -w

use lib '.';
use test_setup;

use Test::More 'no_plan';
use Test::Exception;

BEGIN { use_ok('saliweb::frontend'); }

# Test creating new CompletedJob objects
{
    my $job = new saliweb::frontend::CompletedJob(
                        {name=>'testjob', directory=>'/foo/bar',
                         archive_time=>'2009-01-01 08:45:00'});
    ok(defined $job, 'Test creation of CompletedJob class');
    is($job->name, 'testjob', '   name');
    is($job->directory, '/foo/bar', '   directory');
    is($job->unix_archive_time, 1230799500, '   unix_archive_time');
}

# Test date format parsing
{
    throws_ok {new saliweb::frontend::CompletedJob(
                    {archive_time=>'garbage'})}
              saliweb::frontend::InternalError,
             'CompletedJob should fail on invalid date format';
}
