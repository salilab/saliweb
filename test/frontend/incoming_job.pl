#!/usr/bin/perl -w

use lib '.';
use test_setup;

use Test::More 'no_plan';
use Test::Exception;

BEGIN { use_ok('saliweb::frontend'); }

# Test sanitize_jobname function
{
    is(saliweb::frontend::IncomingJob::_sanitize_jobname("ABC&^abc; 123_-X"),
       "ABCabc123_-X", "sanitize_jobname (chars)");

    is(saliweb::frontend::IncomingJob::_sanitize_jobname(
         "012345678901234567890123456789abcdefghijlk"),
         "012345678901234567890123456789", "                 (length)");
}

# Test generate_random_passwd function
{
    my $str = saliweb::frontend::IncomingJob::generate_random_passwd(10);
    is(length($str), 10, "generate_random_password (10)");
    $str = saliweb::frontend::IncomingJob::generate_random_passwd(20);
    is(length($str), 20, "                         (20)");
}
