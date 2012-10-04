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

    is(saliweb::frontend::IncomingJob::_sanitize_jobname(undef),
       "job", "                 (default, undef)");
    is(saliweb::frontend::IncomingJob::_sanitize_jobname(''),
       "job", "                 (default, empty)");

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
    like($url, qr/^mycgiroot\/results\.cgi\/myjob\?passwd=.{10}$/,
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

# Test _cancel function
{
    my $dir = tempdir( CLEANUP => 0 );
    my $in = {directory=>$dir};
    bless($in, 'saliweb::frontend::IncomingJob');
    ok(-d $dir, "Job directory exists before _cancel");
    $in->_cancel();
    ok(! -d $dir, "Job directory does not exist after _cancel");
    $in->{directory} = '/not/exist';
    dies_ok { $in->_cancel() }
            "_cancel fails on non-existent directory";
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

    # Check old-style (give email to constructor)
    my $job = new saliweb::frontend::IncomingJob($frontend, "myjob", "myemail");
    ok(defined $job, 'Test creation of IncomingJob objects');
    is($job->{email}, 'myemail', '   email');
    like($job->name, qr/^myjob_\d{0,5}0$/, '   name');
    my $jobname = $job->name;
    is($job->directory, "$dir/$jobname", '   directory');
    throws_ok { $job->results_url }
              'saliweb::frontend::InternalError',
              '   cannot get results URL before submit';

    # Check new-style (no email to constructor)
    $job = new saliweb::frontend::IncomingJob($frontend, "myjob");
    is($job->{email}, undef, '   email');
}

# Test resume of IncomingJobs
{
    my $dir = tempdir( CLEANUP => 1 );
    mkdir("$dir/myjob");
    mkdir("$dir/existing-job");
    my $dbh = new Dummy::DB;
    my $config = {};
    $config->{directories}->{INCOMING} = $dir;
    my $frontend = {cgiroot=>'mycgiroot', config=>$config, dbh=>$dbh};
    bless($frontend, 'saliweb::frontend');

    my $job = new saliweb::frontend::IncomingJob($frontend, "myjob");
    my $jobname = $job->name;

    # Should be able to resume any job with an existing directory
    my $resjob = resume saliweb::frontend::IncomingJob($frontend, $jobname);
    is($resjob->name, $jobname);

    $resjob = resume saliweb::frontend::IncomingJob($frontend, "myjob");
    is($resjob->name, "myjob");

    # Check resume_job method
    $resjob = $frontend->resume_job("myjob");
    is($resjob->name, "myjob");

    # Check sanitizing of job names
    $resjob = resume saliweb::frontend::IncomingJob($frontend, "my/*%job");
    is($resjob->name, "myjob");

    # Check handling of database errors
    $dbh->{failprepare} = 1;
    throws_ok { resume saliweb::frontend::IncomingJob($frontend, "myjob") }
              'saliweb::frontend::DatabaseError';
    $dbh->{failprepare} = 0;
    $dbh->{failexecute} = 1;
    throws_ok { resume saliweb::frontend::IncomingJob($frontend, "myjob") }
              'saliweb::frontend::DatabaseError';
    $dbh->{failexecute} = 0;

    throws_ok { resume saliweb::frontend::IncomingJob($frontend, "badjob") }
              'saliweb::frontend::InputValidationError';
    throws_ok { resume saliweb::frontend::IncomingJob($frontend,
                                                      "existing-job") }
              'saliweb::frontend::InputValidationError';
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
    ok(defined $job, "Create IncomingJob for submit via constructor");
    is ($job->{email}, 'myemail',
        'IncomingJob email member');
    is_deeply($frontend->{incoming_jobs}, {$job=>$job},
              "incoming_jobs hash contains key for job");
    $job->submit();
    is_deeply($frontend->{incoming_jobs}, {},
              "incoming_jobs hash no longer contains job key");
    is_deeply($frontend->{submitted_jobs}, [$job],
              "submitted_jobs array now contains job");
    is($dbh->{query}->{execute_calls}, 1,
       "IncomingJob::submit (execute calls)");
    like($job->results_url,
         qr/^mycgiroot\/results\.cgi\/myjob\?passwd=.{10}$/,
         '   results_url');

    $job->{name} = 'fail-job';
    throws_ok { $job->submit() }
              'saliweb::frontend::DatabaseError',
              "                    (failure at execute)";
    like($@, qr/Cannot execute query DB error/,
         "                    (exception message)");
    # Make sure it works with a correct job name and email address
    $job->{name} = 'ok-job';
    $job->submit('otheremail');
    is ($job->{email}, 'otheremail',
        'IncomingJob email in submit');

    # Check make_job method
    my $job2 = $frontend->make_job('myjob', 'myemail');
    ok(defined $job2, "Create IncomingJob for submit via make_job");

    # Now check for failure in prepare
    $dbh->{failprepare} = 1;
    throws_ok { $job->submit() }
              'saliweb::frontend::DatabaseError',
              "                    (failure at prepare)";
    like($@, qr/Cannot prepare query DB error/,
         "                    (exception message)");
}
