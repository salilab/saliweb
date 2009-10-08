package foo;
use base qw(saliweb::frontend);

use strict;

sub new {
    return saliweb::frontend::new(@_, @CONFIGFILE@, "Foo Service");
}
