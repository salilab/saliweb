sub check_page_access {
    my ($self, $page_type) = @_;

    if ($page_type eq 'submit' && !defined($self->user_name)) {
        throw saliweb::frontend::AccessDeniedError(
                     "Only logged-in users are allowed to submit jobs");
    }
}
