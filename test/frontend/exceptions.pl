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
}
