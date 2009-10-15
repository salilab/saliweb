#!/usr/bin/perl -w

use lib '.';
use test_setup;

use Test::More 'no_plan';
use Test::Exception;
use MIME::Lite;
use Test::Output qw(stdout_from);
use Error;
use File::Temp qw(tempdir);
use strict;
use CGI;
use DBI;

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
                user_info=>$user_info, version=>'myversion'};
    bless($self, 'saliweb::frontend');
    is($self->cgi, 'mycgi', 'saliweb::frontend accessors: cgi');
    is($self->htmlroot, 'myhtmlroot', '                             htmlroot');
    is($self->cgiroot, 'mycgiroot', '                             cgiroot');
    is($self->email, 'myemail', '                             email');
    is($self->version, 'myversion', '                             version');
    undef $self->{user_info};
    is($self->email, undef, '                             undef email');
    is($self->modeller_key, undef, '                             modeller_key');
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
    like($out, '/^Status: 413 Request entity too large.*' .
               '<!DOCTYPE html.*<html.*<head>.*<title>CGI error.*' .
               '<body>.*<h2>.*CGI error.*413 Request entity too large.*' .
               '<\/html>/s',
         '                         should return a 413 HTML page');
}

# Test setup_user method
{
    sub test_setup_user {
        my $q = new CGI;
        my $dbh = new Dummy::DB;
        $dbh->{query_class} = "Dummy::UserQuery";
        my $self = {CGI=>$q, dbh=>$dbh};
        bless($self, 'saliweb::frontend');
        $self->_setup_user($dbh);
        return $self;
    }
    sub check_anon_user {
        my ($self, $dbcalls, $msg) = @_;
        ok(exists($self->{'user_name'}) && !defined($self->{'user_name'}),
           "           anonymous user (user_name, $msg)");
        ok(exists($self->{'user_info'}) && !defined($self->{'user_info'}),
           "           anonymous user (user_info, $msg)");
        is($self->{dbh}->{preparecalls}, $dbcalls,
           "           DB accesses (user_info, $msg)");
    }

    # Check valid user (HTTPS, valid cookie)
    $ENV{'HTTPS'} = 'on';
    $ENV{'HTTP_COOKIE'} = 'sali-servers=user_name&test%20user&session&foobar';
    my $self = test_setup_user();
    delete $ENV{'HTTP_COOKIE'};
    delete $ENV{'HTTPS'};
    is($self->{user_name}, 'test user', 'setup_user valid user (user name)');
    is($self->{user_info}->{email}, 'test email',
       '           valid user (email)');

    # Check anonymous user, no cookie, no HTTPS
    $self = test_setup_user();
    check_anon_user($self, 0, 'no cookie, no HTTPS');

    # User validation should fail if the cookie is valid but HTTPS is off
    $ENV{'HTTP_COOKIE'} = 'sali-servers=user_name&test%20user&session&foobar';
    $self = test_setup_user();
    delete $ENV{'HTTP_COOKIE'};
    check_anon_user($self, 0, 'valid cookie, no HTTPS');

    # User validation should fail if HTTPS is on but no cookie is present
    $ENV{'HTTPS'} = 'on';
    $self = test_setup_user();
    delete $ENV{'HTTPS'};
    check_anon_user($self, 0, 'HTTPS, no cookie');

    # User validation should fail if HTTPS is on but the cookie is invalid
    $ENV{'HTTPS'} = 'on';
    $ENV{'HTTP_COOKIE'} =
                  'sali-servers=user_name&test%20user&session&wronghash';
    $self = test_setup_user();
    delete $ENV{'HTTPS'};
    delete $ENV{'HTTP_COOKIE'};
    check_anon_user($self, 1, 'HTTPS, invalid cookie');
}

# Test constructor
{
    my $tmpdir = tempdir( CLEANUP => 1 );
    my $main = "$tmpdir/main.ini";
    my $frontend = "$tmpdir/frontend.ini";

    ok(open(FH, "> $main"), "Open main.ini");
    print FH <<END;
[database]
db=testdb
frontend_config=frontend.ini

[general]
urltop: http://foo.com/mytop
END
    ok(close(FH), "Close main.ini");

    ok(open(FH, "> $frontend"), "Open frontend.ini");
    print FH <<END;
[frontend_db]
user=myuser
passwd=mypasswd
END
    ok(close(FH), "Close frontend.ini");

    my $self = new saliweb::frontend($main, '1.0', 'test_server');
    isa_ok($self, 'saliweb::frontend', 'saliweb::frontend object');
    is($self->{server_name}, 'test_server', 'saliweb::frontend server_name');
    is($self->{rate_limit_period}, 3600, '                  rate_limit_period');
    is($self->{rate_limit}, 10, '                  rate_limit');
    isa_ok($self->{CGI}, 'CGI', '                  CGI');
    is($self->{page_title}, 'test_server', '                  page_title');
    is($self->{version}, '1.0', '                  version');
    is($self->{config}->{general}->{urltop}, 'http://foo.com/mytop',
       '                  config.urltop');
    is($self->{htmlroot}, 'http://foo.com/mytop/html/',
       '                  htmlroot');
    is($self->{cgiroot}, 'http://foo.com/mytop',
       '                  cgiroot');
    is($self->{dbh}, 'dummy DB handle',
       '                  dbh');
    ok(exists($self->{user_info}),
       '                  user_info');
    ok(exists($self->{user_name}),
       '                  user_name');

    # Make sure roots are modified to use https: if we are SSL secured
    $ENV{HTTPS} = 'on';
    $self = new saliweb::frontend($main, '1.0', 'test_server');
    delete $ENV{HTTPS};
    is($self->{config}->{general}->{urltop}, 'http://foo.com/mytop',
       'saliweb::frontend SSL-secured config.urltop');
    is($self->{htmlroot}, 'https://foo.com/mytop/html/',
       '                              htmlroot');
    is($self->{cgiroot}, 'https://foo.com/mytop',
       '                              cgiroot');

    # Make sure setup errors are caught
    stdout_from {
        throws_ok { new saliweb::frontend('/not/exist', '1.0', 'test_server') }
                  "saliweb::frontend::InternalError",
                  "saliweb::frontend constructor fail, no config file";
    };
    like($@, qr#^Cannot open /not/exist: No such file or directory#,
         " " x 51 . "(exception message)");
    like($MIME::Lite::last_email->{Data},
         qr#A fatal error occurred.*Cannot open /not/exist: No such file#s,
         " " x 51 . "(failure email)");

    $DBI::connect_failure = 1;
    stdout_from {
        throws_ok { new saliweb::frontend($main, '1.0', 'test_server') }
                  "saliweb::frontend::DatabaseError",
                  "saliweb::frontend constructor fail, DB connect failure";
    };
    like($@, qr/^Cannot connect to database/,
         " " x 51 . "(exception message)");
    like($MIME::Lite::last_email->{Data},
         qr/A fatal error occurred.*Cannot connect to database/s,
         " " x 51 . "(failure email)");
    $DBI::connect_failure = 0;

    my $ratefile = '/tmp/test_server-service.state';
    ok(-f $ratefile, 'saliweb::frontend updated rate-limit file');
    ok(unlink($ratefile), 'unlink rate-limit file');
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
    like($out, '/^Content\-Type:.*<!DOCTYPE html.*<html.*<head>.*' .
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
    like($out, '/^Content\-Type:.*<!DOCTYPE html.*<html.*<head>.*' .
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
    like($@, qr/Please provide a valid return email/,
              "                     (exception message)");

    throws_ok { check_required_email("") }
              'saliweb::frontend::InputValidationError',
              "                     (\"\")";
    like($@, qr/Please provide a valid return email/,
              "                     (exception message)");

    throws_ok { check_required_email("garbage") }
              'saliweb::frontend::InputValidationError',
              "                     (invalid address)";
    like($@, qr/Please provide a valid return email/,
              "                     (exception message)");

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
    like($@, qr/Please provide a valid return email/,
              "                     (exception message)");

    lives_ok { check_optional_email("test\@test.com") }
              "                     (good address)";
}

# Test check_modeller_key function
{
    throws_ok { check_modeller_key("garbage") }
              'saliweb::frontend::InputValidationError',
              "check_modeller_key (invalid key)";
    like($@, qr/^You have entered an invalid MODELLER key/,
         "                   (exception message)");
    throws_ok { check_modeller_key(undef) }
              'saliweb::frontend::InputValidationError',
              "                   (undef)";
    like($@, qr/^You have entered an invalid MODELLER key/,
         "                   (exception message)");

    lives_ok { check_modeller_key("***REMOVED***") }
             "                   (valid key)";
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
    like($@, qr/my internal error/,
              '                   (exception message)');
              
    my $email = $MIME::Lite::last_email;
    $MIME::Lite::last_email = undef;
    like($email->{Data}, qr/A fatal error occurred in the unittest2\-server.*/,
         '                   (data)');

    $exc = new NoThrowError("my internal error");
    my $out = stdout_from { $self->handle_fatal_error($exc) };
    like($out, 
         '/^Status: 500.*<!DOCTYPE html.*<html.*<head>.*<title>500.*' .
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
