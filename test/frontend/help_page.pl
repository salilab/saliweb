#!/usr/bin/perl -w

use lib '.';
use test_setup;

use Test::More 'no_plan';
use Test::Exception;
use Test::Output qw(stdout_from);
use File::Temp qw(tempdir);
use strict;
use CGI;

BEGIN {
    use_ok('saliweb::frontend');
}

my $tmpdir = tempdir( CLEANUP => 1 );
mkdir("$tmpdir/work");
mkdir("$tmpdir/txt");
chdir("$tmpdir/work");

END {
    chdir("/");
}

# Test get_text_file method
{
    my $cls = {};
    bless($cls, 'saliweb::frontend');
    my $testfile = '../txt/test-text-file';
    ok(open(FH, "> $testfile"), "Open $testfile");
    print FH "test text\n";
    ok(close(FH), "Close $testfile");

    is($cls->get_text_file($testfile),
       "test text\n<div style=\"clear:both;\"></div>", "read text file");

    is($cls->get_text_file("does-not-exist"), '', 'non-existing text file');
}

# Test get_help_page 
{
    my $cls = {};
    bless($cls, 'saliweb::frontend');
    for my $page_type ('contact', 'news', 'faq', 'help') {
        my $testfile = "../txt/${page_type}.txt";
        ok(open(FH, "> $testfile"), "Open $testfile");
        print FH "test $page_type text\n";
        ok(close(FH), "Close $testfile");
        like($cls->get_help_page($page_type),
             "/^test ${page_type} text\$.*<div.*<\/div>\$/ms",
             "get_help_page($page_type)");
    }
    like($cls->get_help_page('garbage'),
         "/^test help text\$.*<div.*<\/div>\$/ms",
         "get_help_page(default=help)");
}

# Test display_help_page
{
    sub get_help_obj {
        my $q = new CGI;
        $q->param('type', shift);
        $q->param('style', shift);
        my $cls = {CGI=>$q, server_name=>'test server'};
        bless($cls, 'saliweb::frontend');
        return $cls;
    }
    my $cls = get_help_obj('news', 'helplink');
    my $out = stdout_from { $cls->display_help_page() };
    like($out,
         "/^Content\-Type:.*<!DOCTYPE html.*<html.*<head>.*" .
         "<title>test server Help</title>.*help\.css.*</head>.*" .
         '<body>' . "\n" .
         "<div id=\"fullpart\">test news text.*" .
         "</body>.*</html>/s", 'check news page, helplink style');
    unlike($out, "/scgi\/server.cgi/",
           '                                (no header)');

    $cls = get_help_obj('contact', 'garbage');
    $out = stdout_from { $cls->display_help_page() };
    like($out,
         "/^Content\-Type:.*<!DOCTYPE html.*<html.*<head>.*" .
         "<title>test server Help</title>.*server\.css.*</head>.*" .
         '<body.*scgi\/server.cgi.*' .
         "<div id=\"fullpart\">test contact text.*" .
         "</body>.*</html>/s", 'check contact page, regular style');
}
