#!/usr/bin/perl -w

use lib '.';
use test_setup;

use Test::More 'no_plan';
use Test::Exception;
use Error;

BEGIN { use_ok('saliweb::frontend'); }

# Test hierarchy of exception classes
{
    isa_ok(saliweb::frontend::InputValidationError, Error::Simple,
           'InputValidationError');
    isa_ok(saliweb::frontend::InternalError, Error::Simple, 'InternalError');
    isa_ok(saliweb::frontend::DatabaseError, Error::Simple, 'DatabaseError');
}
