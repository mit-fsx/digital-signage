#!/usr/bin/perl -w

use strict;
use CGI qw(:standard);
use CGI::Carp qw(fatalsToBrowser);
use File::Copy;
use File::Basename;

my $rootdir = "/var/spool/digital-signage";
my $slidedir = $rootdir . "/slides";
my $thumbdir = $rootdir . "/thumbs";
my $slideuri = "/slides";
my $thumburi = "/thumbs";
my $imconvert = "/usr/bin/convert";

my $debug = exists($ENV{PATH_INFO}) && ($ENV{PATH_INFO} eq '/debug');

sub err {
    print div({-style=>'border: solid thin #000; padding-left: 0.5em; padding-right: 0.5em; background-color: #d23; margin: auto 8em;'}, 
	      p(strong("Error: "), shift));
}


print header('text/html');
print start_html('Digital Signage');

foreach ($slidedir, $thumbdir) {
    (-d $_) || die "Error: $_ is not a directory, cannot continue.";
}

foreach my $filename (param('uploadFile')) {
    next unless ($filename =~ /\w/);
    # TODO: Don't trust the mime type
    my $uinfo = uploadInfo($filename);
    if (exists($uinfo->{'Content-Type'}) &&
	($uinfo->{'Content-Type'} !~ m@^image/(png|jpeg|jpg|gif)$@)) {
	err("Skipping $filename: does not appear to be an image (PNG, JPG, GIF only)");
	next;
    }
    # TODO: actually display errors
    my $destfile = join('/', $slidedir, lc($filename));
    if ( -f $destfile ) {
	err("Skipping: $filename: A slide named $filename exists -- remove it first");
	next;
    }
    if (! copy(tmpFileName($filename), $destfile)) {
	err("Skipping: $filename: Could not copy: $!");
	next;
    }
    my $thumbfile = join('/', $thumbdir, lc($filename));
    if (system($imconvert, $destfile, "-thumbnail", "160x120>", $thumbfile) != 0) {
	err("Successfully uploaded $filename, but could not create thumbnail.");
	next;
    }
}

foreach my $filename (param('removeFile')) {
    unlink join('/', $thumbdir, $filename) || die "Cannot remove thumbnail for $filename";
    unlink join('/', $slidedir, $filename) || die "Cannot remove $filename";
}

my @slides = <$slidedir/*.{png,jpg,jpeg,gif}>;
my @sorted = sort (@slides);

print h2("Found " . scalar(@slides) . " slides");
my $c = 1;
my $rows = [];
print start_form();
foreach my $slide (sort(@slides)) {
    my $uri = $slideuri . "/" . basename($slide);
    my $thuri = $thumburi . "/" . basename($slide);
    $c++;
    push @$rows, td([basename($slide), a({href=>$uri}, img({src=> $thuri})), checkbox(-name=>'removeFile', -value=>basename($slide), -label=>'delete')]);
}
if (scalar(@$rows)) {
    unshift @$rows, th([qw(Filename Thumbnail Remove)]);
    print table(Tr($rows));
}

print h2("Upload files:");
print p("You may upload up to 5 files at a time");
print filefield('uploadFile');
print br;
print filefield('uploadFile');
print br;
print filefield('uploadFile');
print br;
print filefield('uploadFile');
print br;
print filefield('uploadFile');
print submit('Go');
print end_form();

if ($debug) {
    print Dump();
}
print end_html();
exit 0;

