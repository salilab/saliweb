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

$ENV{REQUEST_URI} = "dummy request URI";

# Test help_link method
{
    my $cgi = new CGI;
    my $cls = {CGI=>$cgi, cgiroot=>''};
    bless($cls, 'saliweb::frontend');
    my $link = $cls->help_link('mytarget');

    like($link,
         '/^<a [^>]*onclick="launchHelp\(\'\/help.cgi\?type=' .
         'help&amp;style=helplink#mytarget\'\); return false;"[^>]*>' .
         '<img [^>]*src="\/saliweb\/img\/help\.jpg"[^>]*></a>\s*$/s',
	 "check help_link");
    like($link,
         '/^<a [^>]*href="\/help.cgi\?type=help&amp;style=helplink#mytarget"/s',
         "check help_link href");
}

# Test _google_ua method
{
    my $default = 'UA-44577804-1';
    my $self = {};
    bless($self, 'saliweb::frontend');
    is($self->_google_ua, $default, 'google_ua (default 1)');
    $self->{config} = {};
    is($self->_google_ua, $default, '          (default 2)');
    $self->{config}->{general} = {};
    is($self->_google_ua, $default, '          (default 3)');
    $self->{config}->{general}->{google_ua} = "test_ua";
    is($self->_google_ua, "test_ua", '          (config)');
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
    my $self = {CGI=>new CGI, page_title=>'test page title',
                canonical_url=>'/foo'};
    bless($self, 'saliweb::frontend');
    like($self->start_html(),
         '/<!DOCTYPE html.*<head>.*<title>test page title<\/title>' .
         '.*<link rel="stylesheet" type="text\/css" ' .
         'href="\/saliweb\/css\/server.css" \/>' .
         '.*<script (type="text/JavaScript" )?' .
	 'src="\/saliweb\/js\/salilab\.js".*<\/head>' .
         '.*<body>/s', "start_html (default style)");
    like($self->start_html('mystyle.css'),
         '/<!DOCTYPE html.*<head>.*<title>test page title<\/title>' .
         '.*<link rel="stylesheet".*href="mystyle.css"' .
         '.*<script (type="text/JavaScript" )?' .
         'src="\/saliweb\/js\/salilab\.js".*<\/head>' .
         '.*<body>/s', "           (mystyle)");
}

# Test start_html method with modified header
{
    my $self = {CGI=>new CGI, page_title=>'test page title',
                canonical_url=>'/foo'};
    bless($self, 'Dummy::StartHTMLFrontend');
    like($self->start_html(),
         '/type="text\/css" href="\/saliweb\/css\/server\.css".*' .
         'type="text\/css" href="dummy\.css".*' .
         'script (type="text/JavaScript" )?src="\/saliweb\/js\/salilab\.js".*' .
         'script (type="text/JavaScript" )?src="dummy\.js"/s',
         "start_html (modified header)");
}

# Test simple accessors
{
    my $user_info = {email=>'myemail'};
    my $self = {CGI=>'mycgi', htmlroot=>'myhtmlroot', cgiroot=>'mycgiroot',
                user_info=>$user_info, version=>'myversion',
                http_status=>'200', user_name=>'testuser', dbh=>'dbhandle'};
    bless($self, 'saliweb::frontend');
    is($self->cgi, 'mycgi', 'saliweb::frontend accessors: cgi');
    is($self->htmlroot, 'myhtmlroot', '                             htmlroot');
    is($self->cgiroot, 'mycgiroot', '                             cgiroot');
    is($self->email, 'myemail', '                             email');
    is($self->user_name, 'testuser', '                             user_name');
    is($self->version, 'myversion', '                             version');
    undef $self->{user_info};
    is($self->email, undef, '                             undef email');
    is($self->dbh, 'dbhandle', '                             dbh');
    is($self->modeller_key, undef, '                             modeller_key');
    is($self->http_status, '200',
       '                             get http_status');
    $self->http_status('404');
    is($self->http_status, '404',
       '                             set http_status');
}

# Test URL methods
{
    my $self = {'cgiroot'=>'testroot'};
    bless($self, 'saliweb::frontend');
    is($self->index_url, 'testroot/', 'saliweb::frontend URL (index)');
    is($self->submit_url, 'testroot/submit.cgi',
       '                      (submit)');
    is($self->queue_url, 'testroot/queue.cgi', '                      (queue)');
    is($self->help_url, 'testroot/help.cgi?type=help',
       '                      (help)');
    is($self->news_url, 'testroot/help.cgi?type=news',
       '                      (news)');
    is($self->faq_url, 'testroot/help.cgi?type=faq',
       '                      (FAQ)');
    is($self->links_url, 'testroot/help.cgi?type=links',
       '                      (links)');
    is($self->about_url, 'testroot/help.cgi?type=about',
       '                      (about)');
    is($self->contact_url, 'testroot/help.cgi?type=contact',
       '                      (contact)');
    is($self->results_url, 'testroot/results.cgi',
       '                      (results)');
    is($self->download_url, 'testroot/download.cgi',
       '                      (download)');
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

[frontend:foo]
urltop: http://foo.com/myfootop

[directories]
install: /foo/bar

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
    is($self->version_link, '1.0', '                  version link');
    $self->{config}->{general}->{github} = "http://github.com/foo";
    is($self->version_link, '<a href="http://github.com/foo">1.0</a>',
       '                  version link (github)');
    is($self->{config}->{general}->{urltop}, 'http://foo.com/mytop',
       '                  config.urltop');
    is($self->{htmlroot}, 'http://foo.com/mytop/html/',
       '                  htmlroot');
    is($self->txtdir, '/foo/bar/txt',
       '                  txtdir');
    is($self->{cgiroot}, 'http://foo.com/mytop',
       '                  cgiroot');
    is($self->{dbh}, 'dummy DB handle',
       '                  dbh');
    ok(exists($self->{user_info}),
       '                  user_info');
    ok(exists($self->{user_name}),
       '                  user_name');

    # Check creation of alternate frontend
    $self = new saliweb::frontend($main, '1.0', 'test_foo', 'foo');
    is($self->{server_name}, 'test_foo',
       'saliweb::frontend alternate server_name');
    is($self->{config}->{general}->{urltop}, 'http://foo.com/myfootop',
       '                            urltop');

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

# Test get_lab_navigation_links method
{
    my $self = {CGI=>new CGI};
    bless($self, 'saliweb::frontend');
    my $links = $self->get_lab_navigation_links();
    like($links->[0], qr#<a href=.*>Sali Lab Home</a>#,
         'get_lab_navigation_links');
}

# Test get_header_page_title method
{
    my $self = {page_title=>'test page title'};
    bless($self, 'saliweb::frontend');
    my $header = $self->get_header_page_title();
    like($header, qr#logo_small\.gif.*test page title</h3>#,
         'get_header_page_title');
}

# Test get_header method
{
    my $self = {CGI=>new CGI, page_title=>'header test'};
    bless($self, 'saliweb::frontend');
    like($self->get_header,
         '/<a href="https:\/\/modbase\.compbio\.ucsf\.edu\/scgi\/' .
         'server\.cgi">Login<\/a>/s',
         'header with anonymous user');

    $self->{'user_info'} = 'foo';
    $self->{'user_name'} = '<foo>testuser';
    like($self->get_header,
         '/<a href="https:\/\/modbase\.compbio\.ucsf\.edu\/scgi\/' .
         'server\.cgi">Current User: &lt;foo&gt;testuser<\/a>.*' .
         '<a href="https:\/\/modbase\.compbio\.ucsf\.edu\/scgi\/' .
         'server\.cgi\?logout=true">Logout<\/a>/s',
         '       with logged-in user');

    $self = {CGI=>new CGI, page_title=>'header test', server_name=>'foo',
             cgiroot=>'/foo'};
    bless($self, 'Dummy::Frontend');
    like($self->get_header,
         '/header test.*Link 1.*Link 2 for foo service.*' .
         'Project menu for foo service/s', '       with overridden methods');
    
}

sub make_test_frontend {
    my $self = {CGI=>new CGI, page_title=>'test title',
                rate_limit_checked=>0, server_name=>shift,
                cgiroot=>'http://foo/bar'};
    bless($self, 'Dummy::Frontend');
    return $self;
}

sub test_display_page {
    my $page_type = shift;
    my $title = shift;
    my $status = shift || "";
    if ($status) {
        $status .= ".*";
    }
    my $sub = "display_${page_type}_page";
    my $prefix = ' ' x (length($sub) + 1);
    my $self = make_test_frontend('test');
    my $out = stdout_from { $self->$sub() };
    like($out, "/^$status" .
               'Content\-Type:.*<!DOCTYPE html.*<html.*<head>.*' .
               "<title>$title<\/title>.*<body.*Link 1.*Project menu for.*" .
               "test_${page_type}_page.*<\/html>/s",
         "$sub generates valid complete HTML page");

    $self = make_test_frontend("access${page_type}");
    $out = stdout_from { $self->$sub() };
    like($out, "/^Status: 401.*" .
               'Content\-Type:.*<!DOCTYPE html.*<html.*<head>.*' .
               "<body.*Link 1.*Project menu for.*" .
               "get_${page_type}_page access.*<\/html>/s",
         "${prefix}handles user errors");

    $self = make_test_frontend("checkaccess${page_type}");
    $out = stdout_from { $self->$sub() };
    like($out, "/^Status: 401.*" .
               'Content\-Type:.*<!DOCTYPE html.*<html.*<head>.*' .
               "<body.*Link 1.*Project menu for.*" .
               "access to ${page_type} denied.*<\/html>/s",
         "${prefix}calls check_page_access");

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

# Check failures in get_footer() etc. are caught
{
    my $self = make_test_frontend("failfooter");
    my $out = stdout_from { $self->display_index_page() };
    like($out, '/^Status: 500 Internal Server Error.*' .
               '<!DOCTYPE html.*<html.*<head>.*<body>.*' .
               'footer failure.*<\/html>/s',
         'exception in get_footer() is caught properly');
    is($self->{rate_limit_checked}, 1,
       '                      triggers handle_fatal_error');
    like($MIME::Lite::last_email->{Data}, "/footer failure/",
         '                      sent failure email');
}

# Test display_index_page method
{
    test_display_page('index', 'test title');
}

# Test display_submit_page method
{
    test_display_page('submit', 'test Submission', 'Status: 201 Created');

    my $self = make_test_frontend('invalidsubmit');
    my $out = stdout_from { $self->display_submit_page() };
    like($out, '/^Status: 400 Bad Request.*' .
               'Content\-Type:.*<!DOCTYPE html.*<html.*<head>.*' .
               '<title>invalidsubmit Submission<\/title>.*<body.*Link 1.*' .
               'Project menu for.*bad submission.*<\/html>/s',
         '                    handles invalid submission');

    $self = make_test_frontend('nosubmit');
    stdout_from {
        throws_ok { $self->display_submit_page() }
                  "saliweb::frontend::InternalError",
                  '                    handles no submission';
    };
    like($@, qr/^No job submitted by submit page/,
         '                    (exception message)');

    my $cancel_calls = 0;
    $self = make_test_frontend('incomplete-submit');
    $self->{cancel_calls} = \$cancel_calls;
    $out = stdout_from { $self->display_submit_page() };
    is($cancel_calls, 1,
       '                   cancels incomplete job submissions');

    $cancel_calls = 0;
    $self = make_test_frontend('incomplete-submit-exception');
    $self->{cancel_calls} = \$cancel_calls;
    $out = stdout_from { $self->display_submit_page() };
    is($cancel_calls, 1,
       '                   cancels incomplete jobs even after exceptions');
}

# Test display_queue_page method
{
    test_display_page('queue', 'test Queue');
}

# Test display_help_page method
{
    test_display_page('help', 'test Help');
}

# Test get_footer method
{
    my $self = {CGI=>new CGI};
    bless($self, 'saliweb::frontend');
    is($self->get_footer, "", 'get_footer returns an empty string');
}

# Test default get_*_page methods
{
    my $self = {CGI=>new CGI};
    bless($self, 'saliweb::frontend');
    is($self->get_index_page, "", 'get_index_page returns an empty string');
    is($self->get_submit_page, "", 'get_submit_page returns an empty string');
    is($self->get_download_page, "",
       'get_download_page returns an empty string');
    is($self->get_results_page, "", 'get_results_page returns an empty string');
}

# Test format_user_error method
{
    my $self = {CGI=>new CGI, canonical_url=>'/foo'};
    bless($self, 'saliweb::frontend');
    my $exc = new saliweb::frontend::InputValidationError(
                    "my inpvalid <script>error</script>");
    like($self->format_user_error($exc),
         '/^<h2>.*Invalid input.*<\/h2>.*<b>.*' .
         'An error occurred during your request:.*<\/b>.*' .
         'my inpvalid &lt;script&gt;error&lt;\/script&gt;.*' .
         'browser.*BACK/s',
         'format_user_error');
}

# Test handle_user_error method
{
    my $self = {CGI=>new CGI, page_title=>'testtitle', canonical_url=>'/foo'};
    bless($self, 'saliweb::frontend');
    my $exc = new saliweb::frontend::InputValidationError("my inpvalid error");
    my $out = stdout_from { $self->handle_user_error($exc) };
    like($out,
         '/^Status: 400.*<h2>.*Invalid input.*<\/h2>.*<b>.*' .
         'An error occurred during your request:.*<\/b>.*my inpvalid error.*' .
         'browser.*BACK/s',
         'handle_user_error');

    $exc = new saliweb::frontend::AccessDeniedError("accdenied error");
    $out = stdout_from { $self->handle_user_error($exc) };
    like($out,
         '/^Status: 401.*<h2>.*Invalid input.*<\/h2>.*<b>.*' .
         'An error occurred during your request:.*<\/b>.*accdenied error/s',
         '                  (access denied)');
    unlike($out, '/browser.*BACK/s',
           '                  (access denied)');
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

sub make_test_pdb {
    my $tmpdir = shift;
    mkdir("$tmpdir/xy");
    my $testpdb = "$tmpdir/xy/pdb1xyz.ent";
    ok(open(FH, "> $testpdb"), "open test pdb");
    print FH "ATOM      1  N   ALA C   1      27.932  14.488   4.257  " .
             "1.00 23.91           N\n";
    print FH "ATOM      1  N   ALA D   1      27.932  14.488   4.257  " .
             "1.00 23.91           N\n";
    ok(close(FH), "close test pdb");
    ok(system("gzip $testpdb") == 0, "compress test pdb");
}

# Test get_pdb_code function
{
    my $tmpdir = tempdir( CLEANUP => 1 );
    my $oldroot = $saliweb::frontend::pdb_root;
    $saliweb::frontend::pdb_root = $tmpdir . "/";
    make_test_pdb($tmpdir);

    throws_ok { get_pdb_code("1\@bc", ".") }
              'saliweb::frontend::InputValidationError',
              "get_pdb_code (invalid code)";

    throws_ok { get_pdb_code("1aaaaaa", ".") }
              'saliweb::frontend::InputValidationError',
              "get_pdb_code (non-existing code)";

    is(pdb_code_exists("1aaaaaa"), undef, "pdb_code_exists (false)");
    ok(pdb_code_exists("1xyz"), "pdb_code_exists (true)");

    my $code = get_pdb_code("1xyz", ".");
    is($code, "./pdb1xyz.ent", "get_pdb_code (valid code)");
    ok(unlink('pdb1xyz.ent'),  "                          (unlink)");

    $saliweb::frontend::pdb_root = $oldroot;
}

# Test get_pdb_chains function
{
    my $tmpdir = tempdir( CLEANUP => 1 );
    my $oldroot = $saliweb::frontend::pdb_root;
    $saliweb::frontend::pdb_root = $tmpdir . "/";
    make_test_pdb($tmpdir);

    my $code = get_pdb_chains("1xyz", ".");
    is($code, "./pdb1xyz.ent", "get_pdb_chains (no chains specified)");
    ok(unlink('pdb1xyz.ent'),  "(unlink)");

    $code = get_pdb_chains("1xyz:-", ".");
    is($code, "./pdb1xyz.ent", "get_pdb_chains (all chains requested)");
    ok(unlink('pdb1xyz.ent'),  "(unlink)");

    throws_ok { get_pdb_chains("1xyz:\t", ".") }
              'saliweb::frontend::InputValidationError',
              "get_pdb_chains (invalid chains)";

    throws_ok { get_pdb_chains("1xyz:CDE", ".") }
              'saliweb::frontend::InputValidationError',
              "get_pdb_chains (chain not in PDB)";

    $code = get_pdb_chains("1xyz:C", ".");
    is($code, "./1xyzC.pdb", "get_pdb_chains (C chain)");
    ok(unlink('1xyzC.pdb'),  "(unlink)");

    $code = get_pdb_chains("1xyz:Cd", ".");
    is($code, "./1xyzCD.pdb", "get_pdb_chains (C and D chains)");
    ok(unlink('1xyzCD.pdb'),  "(unlink)");

    $saliweb::frontend::pdb_root = $oldroot;
}

# Test sanitize_filename function
{
    my $f = sanitize_filename("../../../FOO b;&ar=45");
    is($f, "FOObar=45", "sanitize filename");

    $f = sanitize_filename("..foo..ba.r");
    is($f, "foo..ba.r", "sanitize filename, no starting periods");
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

    lives_ok { check_modeller_key("\@MODELLERKEY\@") }
             "                   (valid key)";
}

# Test _check_rate_limit method
{
    my $tmpfile = "/tmp/unittest-server-service.state";
    my $self = {server_name=>'unittest-server', rate_limit_period=>30,
                rate_limit=>10, cgiroot=>'/foo'};
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
                rate_limit=>10, cgiroot=>'/foo'};
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

    # No email should be sent for CGI.pm client errors
    $self->_email_admin_fatal_error("CGI.pm: Server closed socket during " .
                                    "multipart read (client aborted?).");
    is($MIME::Lite::last_email, undef,
       '                        (client error - no email)');

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

# Test format_fatal_error method
{
    my $self = {};
    bless($self, 'saliweb::frontend');
    my $exc = new saliweb::frontend::InternalError("my internal error");
    like($self->format_fatal_error($exc),
         '/^Status: 500.*<!DOCTYPE html.*<html.*<head>.*<title>500.*' .
         '<body>.*<h1>.*500.*A fatal internal error occurred.*' .
         'my internal error.*<\/body>.*<\/html>/s',
         'format_fatal_error');
}

# Test handle_fatal_error method
{
    my $tmpfile = "/tmp/unittest2-server-service.state";
    my $self = {server_name=>'unittest2-server', rate_limit_period=>30,
                rate_limit=>10, cgiroot=>'/foo'};
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

    $exc = new Dummy::NoThrowError("my internal error");
    my $out = stdout_from { $self->handle_fatal_error($exc) };
    like($out, 
         '/^Status: 500.*<!DOCTYPE html.*<html.*<head>.*<title>500.*' .
         '<body>.*<h1>.*500.*A fatal internal error occurred.*' .
         'my internal error.*<\/body>.*<\/html>/s',
         '                   (stdout)');

    ok(unlink($tmpfile), '                   (unlink file)');
}
