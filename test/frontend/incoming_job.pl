#!/usr/bin/perl -w

use lib '.';
use test_setup;

use Test::More 'no_plan';
use Test::Exception;

BEGIN { use_ok('saliweb::frontend'); }

# Test sanitize_jobname function
{
    is(saliweb::frontend::IncomingJob::_sanitize_jobname("ABC&^abc; 123_-X"),
       "ABCabc123_-X", "sanitize_jobname");
}
