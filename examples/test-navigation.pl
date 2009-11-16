use saliweb::Test;
use Test::More 'no_plan';

BEGIN {
    use_ok('modfoo');
}

my $t = new saliweb::Test('modfoo');

# Test get_navigation_links
{
    my $frontend = $t->make_frontend();
    my $links = $frontend->get_navigation_links();
    isa_ok($links, 'ARRAY', 'navigation links');
    like($links->[0], qr#<a href="http://modbase/top/">ModFoo Home</a>#,
         'Index link');
}
