#!/usr/bin/perl -w

use lib '.';
use test_setup;

use Test::More 'no_plan';
use Test::Exception;
use Error;
use CGI;

# Miscellaneous tests of the saliweb::frontend class

BEGIN { use_ok('saliweb::frontend'); }

# Test help_link method
{
    my $cgi = new CGI;
    my $cls = {CGI=>$cgi};
    my $link = saliweb::frontend::help_link($cls, 'mytarget');

    is($link, '<a class="helplink" onclick="launchHelp(\'help.cgi?style=' .
              'helplink&amp;type=help#mytarget\'); return false;" ' .
              'href="help.cgi?style=helplink&amp;type=help#mytarget">' .
              '<img class="helplink" src="/saliweb/img/help.jpg" ' .
              'alt="help" /></a>' . "\n", "check help_link");
}
