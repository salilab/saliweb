package saliweb::DummyIncomingJob;

our @ISA = qw/saliweb::frontend::IncomingJob/;

sub new {
    my ($invocant, $frontend, $given_name, $email) = @_;
    my $class = ref($invocant) || $invocant;
    my $self = {};
    bless($self, $class);
    $self->{frontend} = $frontend;
    $self->{email} = $email;
    $self->{directory} = "incoming";
    $self->{name} = "testjob";
    return $self;
}

sub submit {
}

sub results_url {
    return "dummyURL";
}

1;

package saliweb::DummyFrontend;
our @ISA;

sub set_base_class {
    my ($self, $base) = @_;
    our @ISA = ($base);
}

sub make_job {
    my ($self, $user_jobname, $email) = @_;
    return new saliweb::DummyIncomingJob($self, $user_jobname, $email);
}

sub resume_job {
    my ($self, $user_jobname) = @_;
    return new saliweb::DummyIncomingJob($self, $user_jobname);
}

1;

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
    bless($frontend, 'saliweb::DummyFrontend');
    $frontend->set_base_class($self->{module_name});
    return $frontend;
}

1;
