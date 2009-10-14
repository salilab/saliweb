#!/usr/bin/perl -w

use lib '.';
use test_setup;

use Test::More 'no_plan';
use Test::Exception;
use File::Temp qw(tempdir);
use Dummy;
use strict;

BEGIN { use_ok('saliweb::frontend'); }

# Test sanitize_jobname function
{
    is(saliweb::frontend::IncomingJob::_sanitize_jobname("ABC&^abc; 123_-X"),
       "ABCabc123_-X", "sanitize_jobname (chars)");

    is(saliweb::frontend::IncomingJob::_sanitize_jobname(
         "012345678901234567890123456789abcdefghijlk"),
         "012345678901234567890123456789", "                 (length)");
}

# Test generate_random_passwd function
{
    my $str = saliweb::frontend::IncomingJob::generate_random_passwd(10);
    is(length($str), 10, "generate_random_password (10)");
    $str = saliweb::frontend::IncomingJob::generate_random_passwd(20);
    is(length($str), 20, "                         (20)");
}

# Test try_job_name function
{
    my $dir = tempdir( CLEANUP => 1 );
    mkdir("$dir/existing-dir");
    open(FH, "> $dir/existing-file");
    close FH;
    my $query = new Dummy::Query;
    my $dbh = new Dummy::DB;
    my $config = {};
    $config->{directories}->{INCOMING} = $dir;
    sub try_job_name {
        return saliweb::frontend::IncomingJob::try_job_name(
                                     shift, $query, $dbh, $config);
    }
    my $jobdir;

    # Cannot create a job if the directory already exists
    $jobdir = try_job_name("existing-dir");
    is($jobdir, undef, "try_job_name (existing directory)");
    is($query->{execute_calls}, 0, "             (existing directory, calls)");

    # Cannot create a job if the DB has an entry for it already
    $jobdir = try_job_name("existing-job");
    is($jobdir, undef, "             (existing DB job)");
    is($query->{execute_calls}, 1, "             (existing DB job, calls)");
    $query->{execute_calls} = 0;

    # Test second DB check after mkdir
    $jobdir = try_job_name("justmade-job");
    is($jobdir, undef, "            (just-made DB job)");
    ok(-d "$dir/justmade-job", "            (just-made DB job, dir)");
    is($query->{execute_calls}, 2, "            (just-made DB job, calls)");
    $query->{execute_calls} = 0;

    $jobdir = try_job_name("new-job");
    is($jobdir, "$dir/new-job", "            (successful job)");
    ok(-d "$dir/new-job", "            (successful job, dir)");
    is($query->{execute_calls}, 2, "            (successful job, calls)");
    $query->{execute_calls} = 0;

    # Check errors thrown by $query->execute
    throws_ok { try_job_name("fail-1") }
              'saliweb::frontend::DatabaseError',
              "            exception in first execute";
    like($@, qr/Cannot execute: DB error/,
         "                         (exception message)");
    is($query->{execute_calls}, 1, "                         (execute calls)");
    $query->{execute_calls} = 0;

    throws_ok { try_job_name("fail-2") }
              'saliweb::frontend::DatabaseError',
              "            exception in second execute";
    like($@, qr/Cannot execute: DB error/,
         "                         (exception message)");
    is($query->{execute_calls}, 2, "                         (execute calls)");
    $query->{execute_calls} = 0;

    # Check for mkdir failure
    throws_ok { try_job_name("existing-file") }
              'saliweb::frontend::InternalError',
              "            mkdir failure";
    like($@, qr/Cannot make job directory .*: File exists/,
         "            exception message");
    is($query->{execute_calls}, 1,
       "            mkdir failure (execute calls)");
}

# Test _generate_results_url function
{
    my $frontend = {cgiroot=>'mycgiroot'};
    bless($frontend, 'saliweb::frontend');
    my ($url, $passwd) = saliweb::frontend::IncomingJob::_generate_results_url(
                                           $frontend, "myjob");
    is(length($passwd), 10, "generate_results_url (password length)");
    like($url, qr/^mycgiroot\/results\.cgi\?job=myjob\&amp;passwd=.{10}$/,
         "                     (URL)");
}

# Test _get_job_name_directory
{
    my $dir = tempdir( CLEANUP => 1 );
    mkdir("$dir/existing-dir");
    my $dbh = new Dummy::DB;
    my $config = {};
    $config->{directories}->{INCOMING} = $dir;
    my $frontend = {cgiroot=>'mycgiroot', config=>$config, dbh=>$dbh};
    bless($frontend, 'saliweb::frontend');

    my ($jobname, $jobdir);
    ($jobname, $jobdir) =
          saliweb::frontend::IncomingJob::_get_job_name_directory(
                      $frontend, "my &^! job");
    is($jobname, "myjob", "get_job_name_directory (new job, name)");
    is($jobdir, "$dir/myjob", "                       (new job, directory)");

    ($jobname, $jobdir) =
          saliweb::frontend::IncomingJob::_get_job_name_directory(
                      $frontend, "existing-dir");
    like($jobname, qr/^existing\-dir_\d{0,5}0$/,
         "                       (existing directory)");

    $dbh->{failprepare} = 1;
    throws_ok { saliweb::frontend::IncomingJob::_get_job_name_directory(
                          $frontend, "myjob") }
              'saliweb::frontend::DatabaseError',
              "                       (failure in \$dbh->prepare)";
    like($@, qr/Cannot prepare query DB error/,
         "                       (exception message)");
}

# Test creation of IncomingJob objects
{
    my $dir = tempdir( CLEANUP => 1 );
    mkdir("$dir/myjob");
    my $dbh = new Dummy::DB;
    my $config = {};
    $config->{directories}->{INCOMING} = $dir;
    my $frontend = {cgiroot=>'mycgiroot', config=>$config, dbh=>$dbh};
    bless($frontend, 'saliweb::frontend');
    my $job = new saliweb::frontend::IncomingJob($frontend, "myjob", "myemail");
    ok(defined $job, 'Test creation of IncomingJob objects');
    is($job->{given_name}, 'myjob', '   given_name');
    is($job->{email}, 'myemail', '   email');
    like($job->name, qr/^myjob_\d{0,5}0$/, '   name');
    my $jobname = $job->name;
    is($job->directory, "$dir/$jobname", '   directory');
    like($job->results_url,
         qr/^mycgiroot\/results\.cgi\?job=$jobname\&amp;passwd=.{10}$/,
         '   results_url');
}

# Test submit method
{
    my $dir = tempdir( CLEANUP => 1 );
    my $socket = "$dir/socket";
    my $dbh = new Dummy::DB;
    my $config = {};
    $config->{directories}->{INCOMING} = $dir;
    $config->{general}->{socket} = $socket;
    my $frontend = {cgiroot=>'mycgiroot', config=>$config, dbh=>$dbh};
    bless($frontend, 'saliweb::frontend');
    my $job = new saliweb::frontend::IncomingJob($frontend, "myjob", "myemail");
    ok(defined $job, "Create IncomingJob for submit");
    $job->submit();
    is($dbh->{query}->{execute_calls}, 1,
       "IncomingJob::submit (execute calls)");

    $job->{name} = 'fail-job';
    throws_ok { $job->submit() }
              'saliweb::frontend::DatabaseError',
              "                    (failure at execute)";
    like($@, qr/Cannot execute query DB error/,
         "                    (exception message)");
    # Make sure it works with a correct job name
    $job->{name} = 'ok-job';
    $job->submit();
    # Now check for failure in prepare
    $dbh->{failprepare} = 1;
    throws_ok { $job->submit() }
              'saliweb::frontend::DatabaseError',
              "                    (failure at prepare)";
    like($@, qr/Cannot prepare query DB error/,
         "                    (exception message)");
}
