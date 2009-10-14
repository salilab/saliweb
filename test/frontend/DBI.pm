# Dummy DBI.pm, so that tests work on systems without DBI installed.

package DBI;

our $connect_failure = 0;

sub connect {
    if ($connect_failure) {
        return undef;
    } else {
        return "dummy DB handle";
    }
}

1;
