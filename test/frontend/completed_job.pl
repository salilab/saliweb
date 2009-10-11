#!/usr/bin/perl -w

use lib '.';
use test_setup;

use Test::More 'no_plan';
use Test::Exception;
use POSIX qw(strftime);
use CGI;

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

sub mkjob_with_arc {
    my $secs = shift;
    my $arctime = strftime "%Y-%02m-%02d %02H:%02M:%02S",
                  gmtime(time + $secs);
    return new saliweb::frontend::CompletedJob(
                       {name=>'testjob', directory=>'/foo/bar',
                        archive_time=>$arctime});
}

# Test to_archive_time
{
    my $job = mkjob_with_arc(0);
    is($job->to_archive_time, '0 seconds', 'to_archive_time (0 secs)');
    $job = mkjob_with_arc(1);
    is($job->to_archive_time, '1 second', '                (1 sec)');
    $job = mkjob_with_arc(119);
    is($job->to_archive_time, '119 seconds', '                (119 secs)');
    $job = mkjob_with_arc(120);
    is($job->to_archive_time, '2 minutes', '               (2 mins)');
    $job = mkjob_with_arc(119 * 60);
    is($job->to_archive_time, '119 minutes', '               (119 mins)');
    $job = mkjob_with_arc(120 * 60);
    is($job->to_archive_time, '2 hours', '               (2 hours)');
    $job = mkjob_with_arc(47 * 60 * 60);
    is($job->to_archive_time, '47 hours', '               (47 hours)');
    $job = mkjob_with_arc(48 * 60 * 60);
    is($job->to_archive_time, '2 days', '               (2 days)');
    $job = mkjob_with_arc(100 * 24 * 60 * 60);
    is($job->to_archive_time, '100 days', '               (100 days)');

    $job = new saliweb::frontend::CompletedJob(
                           {name=>'testjob', directory=>'/foo/bar'});
    is($job->to_archive_time, undef, '               (no archival)');
}

# Test get_results_available_time
{
    my $q = new CGI;
    my $job = mkjob_with_arc(0);
    is($job->get_results_available_time($q),
       "<p>\n\tJob results will be available at this URL for " .
       "0 seconds.\n</p>\n", "get_results_available_time (0 secs)");

    $job = new saliweb::frontend::CompletedJob(
                           {name=>'testjob', directory=>'/foo/bar'});
    is($job->get_results_available_time($q), "",
       "                           (no archival)");
}
