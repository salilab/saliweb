#!/usr/bin/perl -w

use lib '.';
use test_setup;
use Dummy;

use Test::More 'no_plan';
use Test::Exception;
use Test::Output qw(stdout_from);
use File::Temp qw(tempdir);
use strict;
use CGI;

BEGIN {
    use_ok('saliweb::frontend');
}

# Test display_download_page
{
    my $cls = {CGI=>new CGI, page_title=>'test title',
               rate_limit_checked=>0, server_name=>'dummy server'};
    bless($cls, 'Dummy::Frontend');
    my $out = stdout_from { $cls->display_download_page() };
    like($out,
         "/^Content\-Type:.*<!DOCTYPE html.*<html.*<head>.*" .
         "<title>dummy server Download</title>.*</head>.*" .
         '<body>.*' .
         "<div id=\"fullpart\">test_download_page</div>.*" .
         "</body>.*</html>/s", 'check download page');
}
