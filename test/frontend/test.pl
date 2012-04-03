#!/usr/bin/perl -w

use lib '.';
use test_setup;

use Test::More 'no_plan';
use strict;

# Miscellaneous tests of the saliweb::Test class

BEGIN {
    use_ok('saliweb::Test');
}

# Test new method
{
    my $t = new saliweb::Test('foo');
    isa_ok($t, 'saliweb::Test', 'new saliweb::Test object');
    is($t->{module_name}, 'foo', 'saliweb::Test module_name member');
}

# Test make_frontend
{
    my $t = new saliweb::Test('foo');
    my $frontend = $t->make_frontend();
    isa_ok($frontend, 'foo', 'frontend object');
    isa_ok($frontend->{CGI}, 'CGI', 'frontend CGI');
    is($frontend->{cgiroot}, 'http://modbase/top', 'frontend cgiroot member');
    is($frontend->{htmlroot}, 'http://modbase/html',
       'frontend htmlroot member');
    is($frontend->{version}, 'testversion', 'frontend version member');
}

package foo;
1;
