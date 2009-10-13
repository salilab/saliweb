#!/usr/bin/perl -w

use lib '.';
use test_setup;

use Test::More 'no_plan';
use Test::Exception;
use CGI;
use Dummy;

# Tests of the saliweb::frontend queue page methods

BEGIN { use_ok('saliweb::frontend'); }

# Test get_queue_key
{
    my $self = {CGI=> new CGI};
    bless($self, 'saliweb::frontend');
    like($self->get_queue_key, qr/INCOMING.*FAILED/s, 'get_queue_key');
}

# Test get_queue_rows
{
    my $q = new CGI;
    my $self = {CGI=>$q};
    bless($self, 'saliweb::frontend');
    my $dbh = new Dummy::DB;
    $dbh->{query_class} = "Dummy::QueueQuery";

    my @rows = $self->get_queue_rows($q, $dbh);
    is(scalar(@rows), 2, "get_queue_rows (length)");
    like($rows[0], qr/<td>.*job1.*<td>.*time1.*<td>.*state1/s,
         "               (content, row 1)");
    like($rows[1], qr/<td>.*job2.*<td>.*time2.*<td>.*state2/s,
         "               (content, row 2)");

    $dbh->{failprepare} = 1;
    throws_ok { $self->get_queue_rows($q, $dbh) }
              saliweb::frontend::DatabaseError,
              "               (prepare error)";

    $dbh->{failprepare} = 0;
    $dbh->{failexecute} = 1;
    throws_ok { $self->get_queue_rows($q, $dbh) }
              saliweb::frontend::DatabaseError,
              "               (execute error)";
}

# Test get_queue_page
{
    my $dbh = new Dummy::DB;
    $dbh->{query_class} = "Dummy::QueueQuery";
    my $self = {CGI=>new CGI, dbh=>$dbh, server_name=>'test server'};
    bless($self, 'saliweb::frontend');

    like($self->get_queue_page,
         '/<h3>.*Current test server Queue.*<\/h3>.*' .
         '<table>.*<tr>.*<th>.*Job ID.*' .
         '<th>.*Submit time \(UTC\).*<th>.*Status.*<\/tr>.*' .
         '<td>.*job1.*<td>.*time1.*<td>.*state1.*' .
         '<td>.*job2.*<td>.*time2.*<td>.*state2.*' .
         'INCOMING.*FAILED/s', 'get_queue_page');
}
