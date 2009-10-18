#!/usr/bin/perl -w

use lib '.';
use test_setup;

use Test::More 'no_plan';
use Test::Exception;
use Error;
use strict;

BEGIN { use_ok('saliweb::frontend'); }

# Test hierarchy of exception classes
{
    isa_ok(new saliweb::frontend::InputValidationError("x"), 'Error::Simple',
           'InputValidationError');
    isa_ok(new saliweb::frontend::InternalError("x"), 'Error::Simple',
           'InternalError');
    isa_ok(new saliweb::frontend::DatabaseError("x"), 'Error::Simple',
           'DatabaseError');

    isa_ok(new saliweb::frontend::ResultsError("x"), 'Error::Simple',
           'ResultsError');
    isa_ok(new saliweb::frontend::ResultsBadURLError("x"),
           'saliweb::frontend::ResultsError', 'ResultsBadURLError');
    isa_ok(new saliweb::frontend::ResultsBadJobError("x"),
           'saliweb::frontend::ResultsError', 'ResultsBadJobError');
    isa_ok(new saliweb::frontend::ResultsBadFileError("x"),
           'saliweb::frontend::ResultsError', 'ResultsBadFileError');
    isa_ok(new saliweb::frontend::ResultsGoneError("x"),
           'saliweb::frontend::ResultsError', 'ResultsGoneError');
    isa_ok(new saliweb::frontend::ResultsStillRunningError("x"),
           'saliweb::frontend::ResultsError', 'ResultsStillRunningError');
}
