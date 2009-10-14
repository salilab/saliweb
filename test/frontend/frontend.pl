#!/usr/bin/perl -w

use lib '.';
use test_setup;

use Test::More 'no_plan';
use Test::Exception;
use MIME::Lite;
use Test::Output qw(stdout_from);
use Error;
use File::Temp;
use strict;
use CGI;

# Miscellaneous tests of the saliweb::frontend class

# Redirect STDIN to a temporary file so older versions of CGI.pm
# have somewhere to read data from
my $stdin_fh = File::Temp->new();
print $stdin_fh "1234567890";
$stdin_fh->close();
open(STDIN, "<", $stdin_fh->filename) or die "can't open tempfile: $!";

my $exitvalue;

BEGIN {
    # Make sure we can catch the result from exit()
    *CORE::GLOBAL::exit = sub { $exitvalue = $_[0] };
    use_ok('saliweb::frontend');
    require Dummy;
}

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

# Test simple accessors
{
    my $user_info = {email=>'myemail'};
    my $self = {CGI=>'mycgi', htmlroot=>'myhtmlroot', cgiroot=>'mycgiroot',
                user_info=>$user_info};
    bless($self, 'saliweb::frontend');
    is($self->cgi, 'mycgi', 'saliweb::frontend accessors: cgi');
    is($self->htmlroot, 'myhtmlroot', '                             htmlroot');
    is($self->cgiroot, 'mycgiroot', '                             cgiroot');
    is($self->email, 'myemail', '                             email');
    undef $self->{user_info};
    is($self->email, undef, '                             undef email');
}

# Test URL methods
{
    my $self = {};
    bless($self, 'saliweb::frontend');
    is($self->index_url, '.', 'saliweb::frontend URL (index)');
    is($self->submit_url, 'submit.cgi', '                      (submit)');
    is($self->queue_url, 'queue.cgi', '                      (queue)');
    is($self->help_url, 'help.cgi?type=help', '                      (help)');
    is($self->news_url, 'help.cgi?type=news', '                      (news)');
    is($self->contact_url, 'help.cgi?type=contact',
       '                      (contact)');
    is($self->results_url, 'results.cgi', '                      (results)');
}


# Test setup_cgi method
{
    my $self = {};
    bless($self, 'saliweb::frontend');
    my $q = $self->_setup_cgi();
    isa_ok($q, 'CGI', 'CGI object');

    # Force failure of creation of CGI object
    $CGI::POST_MAX = 1;
    $ENV{'CONTENT_LENGTH'} = 6;
    my $out = stdout_from { $self->_setup_cgi() };

    # Reset to defaults
    $CGI::POST_MAX = -1;
    delete $ENV{'CONTENT_LENGTH'};

    is($exitvalue, 0, 'setup_cgi with bad input should call exit()');
    $exitvalue = undef;
    like($out, '/Status: 413 Request entity too large.*' .
               '<!DOCTYPE html.*<html.*<head>.*<title>CGI error.*' .
               '<body>.*<h2>.*CGI error.*413 Request entity too large.*' .
               '<\/html>/s',
         '                         should return a 413 HTML page');
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

# Test header method
{
    my $self = {CGI=>new CGI, page_title=>'header test'};
    bless($self, 'saliweb::frontend');
    like($self->header,
         '/<a href="https:\/\/modbase\.compbio\.ucsf\.edu\/scgi\/' .
         'server\.cgi">Login<\/a>/s',
         'header with anonymous user');

    $self->{'user_info'} = 'foo';
    $self->{'user_name'} = 'testuser';
    like($self->header,
         '/<a href="https:\/\/modbase\.compbio\.ucsf\.edu\/scgi\/' .
         'server\.cgi">Current User:testuser<\/a>.*' .
         '<a href="https:\/\/modbase\.compbio\.ucsf\.edu\/scgi\/' .
         'server\.cgi\?logout=true">Logout<\/a>/s',
         '       with logged-in user');

    $self = {CGI=>new CGI, page_title=>'header test', server_name=>'foo'};
    bless($self, 'Dummy::Frontend');
    like($self->header,
         '/header test.*Link 1.*Link 2 for foo service.*' .
         'Project menu for foo service/s', '       with overridden methods');
    
}

sub make_test_frontend {
    my $self = {CGI=>new CGI, page_title=>'test title',
                rate_limit_checked=>0, server_name=>shift};
    bless($self, 'Dummy::Frontend');
    return $self;
}

sub test_display_page {
    my $page_type = shift;
    my $title = shift;
    my $sub = "display_${page_type}_page";
    my $prefix = ' ' x (length($sub) + 1);
    my $self = make_test_frontend('test');
    my $out = stdout_from { $self->$sub() };
    like($out, '/Content\-Type:.*<!DOCTYPE html.*<html.*<head>.*' .
               "<title>$title<\/title>.*<body.*Link 1.*Project menu for.*" .
               "test_${page_type}_page.*<\/html>/s",
         "$sub generates valid complete HTML page");

    $self = make_test_frontend("fail${page_type}");
    throws_ok { stdout_from { $self->$sub() } }
              'saliweb::frontend::InternalError',
              "${prefix}exception is reraised";
    like($@, qr/^get_${page_type}_page failure/,
         "${prefix}exception message");
    is($self->{rate_limit_checked}, 1,
       "${prefix}exception triggered handle_fatal error");
    like($MIME::Lite::last_email->{Data}, "/get_${page_type}_page failure/",
         "${prefix}exception sent failure email");
}

# Test display_index_page method
{
    test_display_page('index', 'test title');
}

# Test display_submit_page method
{
    test_display_page('submit', 'test Submission');

    my $self = make_test_frontend('invalidsubmit');
    my $out = stdout_from { $self->display_submit_page() };
    like($out, '/Content\-Type:.*<!DOCTYPE html.*<html.*<head>.*' .
               '<title>invalidsubmit Submission<\/title>.*<body.*Link 1.*' .
               'Project menu for.*bad submission.*<\/html>/s',
         '                    handles invalid submission');
}

# Test display_queue_page method
{
    test_display_page('queue', 'test Queue');
}

# Test display_help_page method
{
    test_display_page('help', 'test Help');
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
              'saliweb::frontend::InputValidationError',
              "check_required_email (undef)";

    throws_ok { check_required_email("") }
              'saliweb::frontend::InputValidationError',
              "                     (\"\")";

    throws_ok { check_required_email("garbage") }
              'saliweb::frontend::InputValidationError',
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
              'saliweb::frontend::InputValidationError',
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

# Test _email_admin_fatal_error method
{
    my $tmpfile = "/tmp/unittest-server-service.state";
    my $self = {server_name=>'unittest-server', rate_limit_period=>30,
                rate_limit=>10};
    bless($self, 'saliweb::frontend');
    if (-f $tmpfile) {
        unlink $tmpfile;
    }
    my $exc = new saliweb::frontend::InternalError("my internal error");

    $self->_email_admin_fatal_error($exc);
    my $email = $MIME::Lite::last_email;
    $MIME::Lite::last_email = undef;
    is($email->{From}, 'system@salilab.org', 'email_admin_fatal_error (from)');
    is($email->{To}, 'system@salilab.org', '                        (to)');
    is($email->{Subject}, 'Fatal error in unittest-server web service frontend',
       '                        (subject)');
    like($email->{Data},
         '/A fatal error occurred in the unittest\-server.*' .
         'error message.*my internal error/s', 
         '                        (data)');

    # Make a state file that indicates we're about to hit the rate limit
    ok(open(FH, "> $tmpfile"), '                        (make file)');
    printf FH "%d\t%d\n", time() - 20, 10;
    ok(close(FH), '                        (close file)');

    $self->_email_admin_fatal_error($exc);
    $email = $MIME::Lite::last_email;
    $MIME::Lite::last_email = undef;
    like($email->{Data},
         qr/These emails are rate\-limited to 10 every 30 seconds.*/,
         '                        (rate limit reached data)');

    $self->_email_admin_fatal_error($exc);
    is($MIME::Lite::last_email, undef,
       '                        (rate limit exceeded - no email)');
    ok(unlink($tmpfile), '                        (delete file)');
}

# Test handle_fatal_error method
{
    my $tmpfile = "/tmp/unittest2-server-service.state";
    my $self = {server_name=>'unittest2-server', rate_limit_period=>30,
                rate_limit=>10};
    bless($self, 'saliweb::frontend');
    if (-f $tmpfile) {
        unlink $tmpfile;
    }
    my $exc = new saliweb::frontend::InternalError("my internal error");

    throws_ok { my $out = stdout_from { $self->handle_fatal_error($exc) } }
              'saliweb::frontend::InternalError',
              'handle_fatal_error (exception thrown)';
              
    my $email = $MIME::Lite::last_email;
    $MIME::Lite::last_email = undef;
    like($email->{Data}, qr/A fatal error occurred in the unittest2\-server.*/,
         '                   (data)');

    $exc = new NoThrowError("my internal error");
    my $out = stdout_from { $self->handle_fatal_error($exc) };
    like($out, 
         '/Status: 500.*<!DOCTYPE html.*<html.*<head>.*<title>500.*' .
         '<body>.*<h1>.*500.*A fatal internal error occurred.*' .
         'my internal error.*<\/body>.*<\/html>/s',
         '                   (stdout)');

    ok(unlink($tmpfile), '                   (unlink file)');
}

package NoThrowError;
use base qw(Error::Simple);

sub throw {
    # do-nothing throw, so we can catch stdout reliably
}
1;
