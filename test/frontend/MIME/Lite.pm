# Dummy MIME::Lite.pm, so that tests work on systems without it installed.

package MIME::Lite;

our $last_email = undef;

sub new {
    my $class = shift;
    my %keys = @_;
    my $self = \%keys;
    bless($self, $class);
    $last_email = $self;
    return $self;
}

sub send {
}

1;
