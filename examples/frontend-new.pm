package modfoo;
use base qw(saliweb::frontend);

use strict;

sub new {
    return saliweb::frontend::new(@_, "##CONFIG##");
}
