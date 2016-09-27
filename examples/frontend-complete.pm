package modfoo;
use base qw(saliweb::frontend);

use strict;

sub new {
    return saliweb::frontend::new(@_, "##CONFIG##");
}

sub get_navigation_links {
...
}

sub get_project_menu {
...
}

sub get_footer {
...
}

sub get_index_page {
...
}

sub get_submit_page {
...
}

sub get_results_page {
...
}
