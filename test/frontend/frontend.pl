#!/usr/bin/perl -w

use lib '.';
use test_setup;

use Test::More 'no_plan';
use Test::Exception;
use Error;
use CGI;

# Miscellaneous tests of the saliweb::frontend class

BEGIN { use_ok('saliweb::frontend'); }

# Test help_link method
{
    my $cgi = new CGI;
    my $cls = {CGI=>$cgi};
    my $link = saliweb::frontend::help_link($cls, 'mytarget');

    is($link, '<a class="helplink" onclick="launchHelp(\'help.cgi?style=' .
              'helplink&amp;type=help#mytarget\'); return false;" ' .
              'href="help.cgi?style=helplink&amp;type=help#mytarget">' .
              '<img class="helplink" src="/saliweb/img/help.jpg" ' .
              'alt="help" /></a>' . "\n", "check help_link");
}

# Test _admin_email method
{
    my $default = 'system@salilab.org';
    my $self = {};
    bless($self, 'saliweb::frontend');
    is($self->_admin_email, $default, 'admin_email (default 1)');
    $self->{config} = {};
    is($self->_admin_email, $default, '            (default 2)');
    $self->{config}->{general} = {};
    is($self->_admin_email, $default, '            (default 3)');
    $self->{config}->{general}->{admin_email} = "myemail";
    is($self->_admin_email, "myemail", '            (config)');
}

# Test set_page_title method
{
    my $self = {server_name=>'myserver'};
    bless($self, 'saliweb::frontend');
    $self->set_page_title("test page");
    is($self->{page_title}, "myserver test page", 'set_page_title');
}

# Test start_html method
{
    my $self = {CGI=>new CGI, page_title=>'test page title'};
    bless($self, 'saliweb::frontend');
    like($self->start_html(),
         '/<!DOCTYPE html.*<head>.*<title>test page title<\/title>' .
         '.*<link rel="stylesheet" type="text\/css" ' .
         'href="\/saliweb\/css\/server.css" \/>' .
         '.*<script src="\/saliweb\/js\/salilab\.js".*<\/head>' .
         '.*<body onload=/s', "start_html (default style)");
    like($self->start_html('mystyle.css'),
         '/<!DOCTYPE html.*<head>.*<title>test page title<\/title>' .
         '.*<link rel="stylesheet".*href="mystyle.css"' .
         '.*<script src="\/saliweb\/js\/salilab\.js".*<\/head>' .
         '.*<body onload=/s', "           (mystyle)");
}

# Test end_html method
{
    my $self = {CGI=>new CGI};
    bless($self, 'saliweb::frontend');
    like($self->end_html(), qr/<\/body>.*<\/html>/s, "end_html");
}

# Test get_projects method
{
    my $self = {CGI=>new CGI};
    bless($self, 'saliweb::frontend');
    my $proj = $self->get_projects();
    is(%$proj, 0, 'get_projects returns an empty hashref');
}

# Test get_project_menu method
{
    my $self = {CGI=>new CGI};
    bless($self, 'saliweb::frontend');
    is($self->get_project_menu, "", 'get_project_menu returns an empty string');
}

# Test get_navigation_links method
{
    my $self = {CGI=>new CGI};
    bless($self, 'saliweb::frontend');
    my $links = $self->get_navigation_links();
    is(@$links, 0, 'get_navigation_links returns an empty arrayref');
}

# Test footer method
{
    my $self = {CGI=>new CGI};
    bless($self, 'saliweb::frontend');
    is($self->footer, "", 'footer returns an empty string');
}

# Test format_input_validation_error method
{
    my $self = {CGI=>new CGI};
    bless($self, 'saliweb::frontend');
    my $exc = new saliweb::frontend::InputValidationError("my inpvalid error");
    like($self->format_input_validation_error($exc),
         '/<h2>.*Invalid input.*<\/h2>.*<b>.*' .
         'An error occurred during your request:.*<\/b>.*my inpvalid error/s',
         'format_input_validation_error');
}

# Test check_required_email method
{
    throws_ok { check_required_email(undef) }
              saliweb::frontend::InputValidationError,
              "check_required_email (undef)";

    throws_ok { check_required_email("") }
              saliweb::frontend::InputValidationError,
              "                     (\"\")";

    throws_ok { check_required_email("garbage") }
              saliweb::frontend::InputValidationError,
              "                     (invalid address)";

    lives_ok { check_required_email("test\@test.com") }
              "                     (good address)";
}

# Test check_optional_email method
{
    lives_ok { check_optional_email(undef) }
             "check_optional_email (undef)";

    lives_ok { check_optional_email("") }
             "                     (\"\")";

    throws_ok { check_optional_email("garbage") }
              saliweb::frontend::InputValidationError,
              "                     (invalid address)";

    lives_ok { check_optional_email("test\@test.com") }
              "                     (good address)";
}

# Test _check_rate_limit method
{
    my $tmpfile = "/tmp/unittest-server-service.state";
    my $self = {server_name=>'unittest-server', rate_limit_period=>30,
                rate_limit=>10};
    bless($self, 'saliweb::frontend');
    if (-f $tmpfile) {
        unlink $tmpfile;
    }
    my ($count, $limit, $period);
    ($count, $limit, $period) = $self->_check_rate_limit;
    is($count, 1, 'check_rate_limit (no file, count)');
    is($limit, 10, '                 (no file, limit)');
    is($period, 30, '                 (no file, period)');
    ok(open(FH, $tmpfile), '                 (no file, open file)');
    like(<FH>, qr/\d+\t2$/, '                 (no file, file contents)');
    ok(close(FH), '                 (no file, close file)');

    ($count, $limit, $period) = $self->_check_rate_limit;
    is($count, 2, '                 (existing file, count)');
    ok(unlink($tmpfile), '                 (delete file)');

    ok(open(FH, "> $tmpfile"), '                 (new file, open file)');
    printf FH "%d\t%d\n", time() - 40, 20;
    ok(close(FH), '                 (new file, close file)');

    ($count, $limit, $period) = $self->_check_rate_limit;
    is($count, 1, '                 (expired file, count)');
    ok(unlink($tmpfile), '                 (delete file)');
}
