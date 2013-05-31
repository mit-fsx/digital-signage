#!/usr/bin/perl

$|=1;

use strict;
use lib '/usr/lib/digital-signage/perl5';
use SharpLCD;
use CGI qw(:standard);

print header, start_html('LCD Control');

my $lcd = new SharpLCD("/dev/ttyUSB0");

if (param('On')) {
    print $lcd->set('POWR', '1') ? 'Turned on OK' : 'Failed to turn on';
} elsif (param('Off')) {
    print $lcd->set('POWR', '0') ? 'Turned off OK' : 'Failed to turn off';
}
print p(sprintf("Current status: LCD is %s", $lcd->get('POWR') ? 'on' : 'off'));
print start_form;
print submit('On'), submit('Off');
print end_form;
print end_html;
