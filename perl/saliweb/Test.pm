package saliweb::Test;

sub new {
    my ($invocant, $module_name) = @_;
    my $class = ref($invocant) || $invocant;
    my $self = {module_name=>$module_name};
    bless($self, $class);
    return $self;
}

sub make_frontend {
    my ($self) = @_;
    my $cgi = new CGI;
    my $frontend = {CGI=>$cgi, cgiroot=>'http://modbase/top',
                    htmlroot=>'http://modbase/html', version=>'testversion'};
    bless($frontend, $self->{module_name});
    return $frontend;
}

1;
