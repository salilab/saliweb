#!/usr/bin/perl -w

use lib '.';
use test_setup;

use Test::More 'no_plan';
use Test::Exception;
use File::Temp qw(tempdir);
use CGI;
use Dummy;
use strict;

# Tests of the saliweb::frontend queue page methods

BEGIN { use_ok('saliweb::frontend'); }

# Test get_queue_key
{
    my $config = {limits=>{running=>10}};
    my $self = {CGI=> new CGI, config=>$config};
    bless($self, 'saliweb::frontend');
    like($self->get_queue_key,
         qr/INCOMING.*No more than 10 jobs may.*QUEUED.*RUNNING.*FAILED/s,
         'get_queue_key (10 jobs)');

    $config = {limits=>{running=>1}};
    $self = {CGI=> new CGI, config=>$config};
    bless($self, 'saliweb::frontend');
    like($self->get_queue_key,
         qr/INCOMING.*No more than 1 job may.*QUEUED.*RUNNING.*FAILED/s,
         '              (1 job)');
}

# Test get_queue_rows
{
    my $q = new CGI;
    my $self = {CGI=>$q, cgiroot=>'testroot'};
    bless($self, 'saliweb::frontend');
    my $dbh = new Dummy::DB;
    $dbh->{query_class} = "Dummy::QueueQuery";

    # Mark one of the running jobs as RUNNING (job-state exists) and the other
    # as QUEUED (file does not exist)
    my $tmpdir = tempdir( CLEANUP => 1 );
    $dbh->{jobdir} = $tmpdir;
    ok(open(FH, "> $tmpdir/job-state"), "Open job-state");
    ok(close(FH), "Close job-state");

    my @rows = $self->get_queue_rows($q, $dbh);
    is(scalar(@rows), 6, "get_queue_rows (length)");
    like($rows[0], qr/<td>.*job1.*<td>.*time1.*<td>.*RUNNING/s,
         "               (content, row 1)");
    like($rows[1], qr/<td>.*job2.*<td>.*time2.*<td>.*QUEUED/s,
         "               (content, row 2)");

    $dbh->{failprepare} = 1;
    throws_ok { $self->get_queue_rows($q, $dbh) }
              'saliweb::frontend::DatabaseError',
              "               (prepare error)";
    like($@, qr/Couldn't prepare query: DB error/,
         "               (exception message)");
    $dbh->{failprepare} = 0;

    $dbh->{failexecute} = 1;
    throws_ok { $self->get_queue_rows($q, $dbh) }
              'saliweb::frontend::DatabaseError',
              "               (execute error)";
    like($@, qr/Couldn't execute query: DB error/,
         "               (exception message)");
    $dbh->{failexecute} = 0;

    $self->{user_name} = 'testuser';
    @rows = $self->get_queue_rows($q, $dbh);
    is(scalar(@rows), 6, "get_queue_rows with user (length)");
    for (my $i = 0; $i < 6; $i++) {
        if ($i == 3) {
            like($rows[3], '/<td><a href="testroot\/results.cgi\/job4\?' .
                           'passwd=testpw">job4<\/a>.*<\/td>.*' .
                           '2009\-10\-01.*COMPLETED/s',
                   "                         (content, row 4)");
        } else {
            unlike($rows[$i], qr/<a href/,
                   "                         (content, row " . ($i + 1) . ")");
        }
    }
}

# Test get_queue_page
{
    my $dbh = new Dummy::DB;
    $dbh->{query_class} = "Dummy::QueueQuery";
    $dbh->{jobdir} = "/";
    my $config = {limits=>{running=>10}};
    my $self = {CGI=>new CGI, dbh=>$dbh, server_name=>'test server',
                config=>$config};
    bless($self, 'saliweb::frontend');

    like($self->get_queue_page,
         '/<h3>.*Current test server Queue.*<\/h3>.*' .
         '<table>.*<tr>.*<th>.*Job ID.*' .
         '<th>.*Submit time \(UTC\).*<th>.*Status.*<\/tr>.*' .
         '<td>.*job1.*<td>.*time1.*<td>.*QUEUED.*' .
         '<td>.*job2.*<td>.*time2.*<td>.*QUEUED.*' .
         '<td>.*job3.*<td>.*time3.*<td>.*INCOMING.*' .
         'INCOMING.*FAILED/s', 'get_queue_page');
}
