#!/usr/bin/perl -w

use lib '.';
use test_setup;

use Test::More 'no_plan';
use Test::Exception;
use File::Temp qw(tempdir);

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
    my $query = new DummyQuery;
    my $dbh = new DummyDB;
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
              saliweb::frontend::DatabaseError,
              "             exception in first execute";
    is($query->{execute_calls}, 1, "                          (execute calls)");
    $query->{execute_calls} = 0;

    throws_ok { try_job_name("fail-2") }
              saliweb::frontend::DatabaseError,
              "             exception in second execute";
    is($query->{execute_calls}, 2, "                          (execute calls)");
    $query->{execute_calls} = 0;

    # Check for mkdir failure
    throws_ok { try_job_name("existing-file") }
              saliweb::frontend::InternalError,
              "             mkdir failure";
    is($query->{execute_calls}, 1,
       "             mkdir failure (execute calls)");
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


package DummyQuery;

sub new {
    my $self = {};
    bless($self, shift);
    $self->{execute_calls} = 0;
    return $self;
}

sub execute {
    my ($self, $jobname) = @_;
    $self->{jobname} = $jobname;
    $self->{execute_calls}++;
    my $calls = $self->{execute_calls};
    if ($jobname eq "fail-$calls") {
        return undef;
    }
    return $jobname ne "fail-job";
}

sub fetchrow_array {
    my $self = shift;
    if ($self->{jobname} eq "existing-job") {
        return (1);
    } elsif ($self->{jobname} eq "justmade-job"
             and $self->{execute_calls} > 1) {
        return (1);
    } else {
        return (0);
    }
}

1;

package DummyDB;

sub new {
    my $self = {};
    bless($self, shift);
    return $self;
}

sub errstr {
    my $self = shift;
    return "DB error";
}
