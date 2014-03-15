#!/usr/bin/perl -w

use lib '.';
use test_setup;

use Test::More 'no_plan';
use Test::Exception;
use Test::Output qw(stdout_from stdout_is);
use File::Temp qw(tempdir);
use MIME::Lite;
use Error;
use CGI;
use IO::Zlib;
use Dummy;
use strict;

# Tests of the saliweb::frontend results page methods

BEGIN { use_ok('saliweb::frontend'); }

# Test allow_file_download
{
    my $cls = {};
    for my $file ("foo", "bar", "/abspath/foo") {
        is(saliweb::frontend::allow_file_download($cls, $file), 1,
           "check allow_file_download: $file");
    }
}

# Test get_file_mime_type
{
    my $cls = {};
    for my $file ("foo", "bar", "/abspath/foo") {
        is(saliweb::frontend::get_file_mime_type($cls, $file), 'text/plain',
           "check get_file_mime_type: $file");
    }
}

# Test download_real_file
{
    my $q = new CGI;
    my $cls = {};
    bless($cls, 'saliweb::frontend');
    my $fh = File::Temp->new();
    print $fh "test\nfile";
    $fh->close() or die "Cannot close $fh: $!";

    stdout_is { $cls->_download_real_file($q, $fh->filename) }
              "Content-Type: text/plain; charset=ISO-8859-1\r\n\r\n" .
              "test\nfile",
              "test download_real_file";

    throws_ok { $cls->_download_real_file($q, "/not/exist") }
              'saliweb::frontend::InternalError',
              "test download_real_file on non-existing file";
    like($@, qr#Cannot open /not/exist: No such file or directory#,
         "                                        (exception message)");
}

# Test download_real_file_gzip
{
    my $q = new CGI;
    my $cls = {};
    bless($cls, 'saliweb::frontend');
    my $dir = File::Temp->newdir();
    my $fh = IO::Zlib->new("$dir/test.gz", "wb") or die "Cannot open: $!";
    print $fh "test\nfile";
    $fh->close() or die "Cannot close $fh: $!";

    stdout_is { $cls->_download_real_file_gzip($q, "$dir/test") }
              "Content-Type: text/plain; charset=ISO-8859-1\r\n\r\n" .
              "test\nfile",
              "test download_real_file_gzip";

    throws_ok { $cls->_download_real_file_gzip($q, "/not/exist") }
              'saliweb::frontend::InternalError',
              "test download_real_file_gzip on non-existing file";
    like($@, qr#Cannot open /not/exist.gz: No such file or directory#,
         "                                        (exception message)");
}

sub make_test_frontend {
    my $q = new CGI;
    $q->path_info('/' . (shift() || ''));
    $q->param('passwd', shift);
    my $dbh = new Dummy::DB;
    $dbh->{query_class} = 'Dummy::ResultsQuery';
    my $cls = {CGI=>$q, dbh=>$dbh, server_name=>'test', cgiroot=>'testcgiroot'};
    bless($cls, 'Dummy::Frontend');
    return $cls;
}

# Test display_results_page
{
    sub check_missing_job_passwd {
        my $cls = make_test_frontend(shift, shift);
        my $out = stdout_from { $cls->display_results_page() };
        like($out, '/^Status: 400 Bad Request.*' .
                   'Content\-Type:.*<!DOCTYPE html.*<html.*<head>.*' .
                   '<title>test Results<\/title>.*<body.*' .
                   'Missing job name and password.*<\/html>/s',
             "                     (" . shift() . ")");
    }
    my $cls = make_test_frontend('testjob', 'testpasswd');
    $cls->{dbh}->{failprepare} = 1;
    stdout_from {
        throws_ok { $cls->display_results_page() }
                  'saliweb::frontend::DatabaseError',
                  'display_results_page (database prepare failure)';
    };
    like($@, qr/^Couldn't prepare query/,
         '                     (exception subtype)');

    check_missing_job_passwd(undef, undef, 'missing job and passwd');
    check_missing_job_passwd('myjob', undef, 'missing passwd');
    check_missing_job_passwd(undef, 'mypasswd', 'missing job');

    $cls = make_test_frontend('testjob', 'testpasswd');
    $cls->{dbh}->{failexecute} = 1;
    stdout_from {
        throws_ok { $cls->display_results_page() }
                    'saliweb::frontend::DatabaseError',
                    '                     (database execute failure)';
    };
    like($@, qr/^Couldn't execute query/,
         '                     (exception subtype)');

    $cls = make_test_frontend('not-exist-job', 'passwd');
    my $out = stdout_from { $cls->display_results_page() };
    like($out, '/^Status: 400 Bad Request.*' .
               'Content\-Type:.*<!DOCTYPE html.*<html.*<head>.*' .
               '<title>test Results<\/title>.*<body.*Link 1.*' .
               'Project menu for.*Job does not exist,' .
               ' or wrong password\..*<\/html>/s',
         '                     (non-existing job)');

    $cls = make_test_frontend('running-job', 'passwd');
    $out = stdout_from { $cls->display_results_page() };
    like($out, '/^Status: 503 Service Unavailable.*' .
               'Content\-Type:.*<!DOCTYPE html.*<html.*<head>.*' .
               '<title>test Results<\/title>.*<body.*Link 1.*' .
               'Project menu for.*Job \'running\-job\' has not yet ' .
               'completed.*check on the status.*queue\.cgi.*<\/html>/s',
         '                     (still running job)');

    $cls = make_test_frontend('archived-job', 'passwd');
    $out = stdout_from { $cls->display_results_page() };
    like($out, '/^Status: 410 Gone.*' .
               'Content\-Type:.*<!DOCTYPE html.*<html.*<head>.*' .
               '<title>test Results<\/title>.*<body.*Link 1.*' .
               'Project menu for.*Results for job \'archived\-job\' are no ' .
               'longer available.*<\/html>/s',
         '                     (archived job)');

    $cls = make_test_frontend('expired-job', 'passwd');
    $out = stdout_from { $cls->display_results_page() };
    like($out, '/^Status: 410 Gone.*' .
               'Content\-Type:.*<!DOCTYPE html.*<html.*<head>.*' .
               '<title>test Results<\/title>.*<body.*Link 1.*' .
               'Project menu for.*Results for job \'expired\-job\' are no ' .
               'longer available.*<\/html>/s',
         '                     (expired job)');

    $cls = make_test_frontend('testjob', 'passwd');
    $out = stdout_from { $cls->display_results_page() };
    like($out, '/^Content\-Type:.*<!DOCTYPE html.*<html.*<head>.*' .
               '<title>test Results<\/title>.*<body.*Link 1.*' .
               'Project menu for.*test_results_page ' .
               'saliweb::frontend::CompletedJob testjob.*<\/html>/s',
         '                     (completed job)');

    $cls = make_test_frontend('testjob', 'passwd');
    $cls->{server_name} = 'failresults';
    stdout_from {
        throws_ok { $cls->display_results_page() }
                  'saliweb::frontend::InternalError',
                  '                     (caught get_results_page exception)';
    };
    like($@, qr/^get_results_page failure/,
         '                     (exception message)');
    is($cls->{rate_limit_checked}, 1,
       '                     (exception triggered handle_fatal error)');
    like($MIME::Lite::last_email->{Data}, "/get_results_page failure/",
         '                     (exception sent failure email)');

    # Check handling of user errors (e.g. permission denied)
    $cls = make_test_frontend('testjob', 'testpasswd');
    $cls->{server_name} = 'checkaccess';
    $out = stdout_from { $cls->display_results_page() };
    like($out, '/access to results denied/',
         '                     (user error)');
}

# Check file downloads
{
    sub make_test_results_file {
        my $cls = make_test_frontend('testjob', 'passwd');
        $cls->{CGI}->path_info($cls->{CGI}->path_info . '/' . (shift() || ''));
        return $cls;
    }

    my $tmpdir = tempdir( CLEANUP => 1 );
    my $testfile = "$tmpdir/testfile";
    ok(open(FH, "> $testfile"), '                     (open testfile)');
    print FH "test text\n";
    ok(close(FH), '                     (close testfile)');

    ok(mkdir("$tmpdir/subdir"), '                     (make subdir)');
    my $subtestfile = "$tmpdir/subdir/testfile";
    ok(open(FH, "> $subtestfile"), '                     (open subtestfile)');
    print FH "other test\n";
    ok(close(FH), '                     (close testfile)');

    # substr forces relative path to /tmp/
    my $cls = make_test_results_file(substr($testfile, 5));
    my $out = stdout_from { $cls->display_results_page() };
    like($out, '/^Content-Type: text\/plain;.*test text/s',
         '                     (download valid file)');

    # Check file in subdirectory
    $cls = make_test_results_file(substr($subtestfile, 5));
    $out = stdout_from { $cls->display_results_page() };
    like($out, '/^Content-Type: text\/plain;.*other test/s',
         '                     (download subdir valid file)');

    sub check_invalid_file {
        my $cls = make_test_results_file(shift);
        my $out = stdout_from { $cls->display_results_page() };
        # Note that queue page link is absolute, since we may be in a
        # 'subdirectory' of the results page.
        like($out, '/^Status: 404 Not Found.*' .
                   'Content\-Type:.*<!DOCTYPE html.*<html.*<head>.*' .
                   '<title>test Results<\/title>.*<body.*Link 1.*' .
                   'Project menu for.*Invalid results file.*' .
                   'You can check on the status of all jobs.*' .
                   '<a href="testcgiroot\/queue\.cgi">' .
                   'queue.*page.*<\/html>/s',
             '                     (' . shift() . ')');
    }

    check_invalid_file($testfile, 'download file with absolute path');
    check_invalid_file('/not/exist', 'download non-existing file');
    check_invalid_file("../$testfile", 'download file containing ..');
}
