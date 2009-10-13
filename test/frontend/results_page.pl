#!/usr/bin/perl -w

use lib '.';
use test_setup;

use Test::More 'no_plan';
use Test::Exception;
use Test::Output qw(stdout_from stdout_is);
use File::Temp;
use Error;
use CGI;
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

# Test download_file
{
    my $q = new CGI;
    my $cls = {};
    bless($cls, 'saliweb::frontend');
    my $fh = File::Temp->new();
    print $fh "test\nfile";
    $fh->close() or die "Cannot close $fh: $!";

    stdout_is { $cls->download_file($q, $fh->filename) }
              "Content-Type: text/plain; charset=ISO-8859-1\r\n\r\n" .
              "test\nfile",
              "test download_file";

    throws_ok { $cls->download_file($q, "/not/exist") }
              'saliweb::frontend::InternalError',
              "test download_file on non-existing file";
}
