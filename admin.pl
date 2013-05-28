#!/usr/bin/perl -w

use strict;
use CGI qw(:standard);
use CGI::Carp qw(fatalsToBrowser);
use File::Copy;
use File::Basename;

my $rootdir = "/var/signage";
my $slidedir = $rootdir . "/slides";
my $thumbdir = $slidedir . "/thumbs";
my $slideuri = "/slides";
my $imconvert = "/usr/bin/convert";

my $debug = exists($ENV{PATH_INFO}) && ($ENV{PATH_INFO} eq '/debug');

print header('text/html');
print start_html('Digital Signage');

foreach ($slidedir, $thumbdir) {
    (-d $_) || die "Error: $_ is not a directory, cannot continue.";
}

foreach my $filename (param('uploadFile')) {
    next unless ($filename =~ /\w/);
    my $uinfo = uploadInfo($filename);
    if (exists($uinfo->{'Content-Type'}) &&
	($uinfo->{'Content-Type'} !~ m@^image/(png|jpeg|jpg|gif)$@)) {
	print "Error: PNG, JPG, JPEG, or GIF only";
	last;
    }
    my $destfile = join('/', $slidedir, lc($filename));
    if ( -f $destfile ) {
	print "$filename exists, remove it first";
	last;
    }
    if (! copy(tmpFileName($filename), $destfile)) {
	print "Error: File exists.  Remove first.  Copy failed!";
	last;
    }
    my $thumbfile = join('/', $thumbdir, lc($filename));
    if (system($imconvert, $destfile, "-thumbnail", "160x120>", $thumbfile) != 0) {
	print "Error: Thumbnail creation failed.";
	last;
    }
}

foreach my $filename (param('removeFile')) {
    unlink join('/', $thumbdir, $filename) || die "Cannot remove thumbnail for $filename";
    unlink join('/', $slidedir, $filename) || die "Cannot remove thumbnail for $filename";
}

my @slides = <$slidedir/*.{png,jpg,jpeg,gif}>;
my @sorted = sort (@slides);

print h2("Found " . scalar(@slides) . " slides");
my $c = 1;
my $rows = [];
print start_form();
foreach my $slide (sort(@slides)) {
    my $uri = "/slides/" . basename($slide);
    my $thumburi = "/slides/thumbs/" . basename($slide);
    $c++;
    push @$rows, td([basename($slide), a({href=>$uri}, img({src=> $thumburi})), checkbox(-name=>'removeFile', -value=>basename($slide), -label=>'delete')]);
}
if (scalar(@$rows)) {
    unshift @$rows, th([qw(Filename Image Remove)]);
    print table(Tr($rows));
}

print h2("Upload files:");
print filefield('uploadFile');
print submit('Go');
print end_form();
if ($debug) {
    print Dump();
}
print end_html();
exit 0;

