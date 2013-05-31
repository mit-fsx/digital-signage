package SharpLCD;

use strict;

use Carp;
use Device::SerialPort;

sub new {
    my $proto = shift;
    my $dev = shift;
    my $debug = shift || 0;
    my $class = ref($proto) || $proto;
    my $self = {};
    $self->{_port} = Device::SerialPort->new("/dev/ttyUSB0");
    $self->{_port}->databits(8);
    $self->{_port}->baudrate(9600);
    $self->{_port}->stopbits(1);
    $self->{_port}->parity("none");
    $self->{_port}->handshake("none");
    $self->{_port}->stty_icanon(1);
    $self->{_port}->write_settings;
    $self->{_debug} = $debug;

    # Set the characters that terminate each response
    $self->{_port}->are_match("\r\n");

    bless ($self, $class);
    return $self;
}

sub _getResponse {
    my $self = shift;
    my $rv = "";
    until ("" ne $rv) {
	$rv = $self->{_port}->lookfor;
	last unless defined($rv);
	last if $rv;
	sleep 1;
    }
    return $rv;
}

sub _send {
    my $self = shift;
    my @params = @_;
    my $output = join('', @params) . "\r\n";
    if ($self->{_debug}) {
	printf "D: Sending: [%s]\n", join(', ', unpack('C*', $output));
    }
    $self->{_port}->write($output);
}

sub get {
    my $self = shift;
    my $param = shift || '';
    $param = uc($param);
    carp "Invalid parameter ($param)" if (length($param) != 4);
    $self->_send($param, sprintf("%4s", '?'));
    my $r = $self->_getResponse();
    croak "Undefined response" unless defined($r);
    if ($self->{_debug}) {
	printf "D: Response: [%s]\n", join(', ', unpack('C*', $r));
    }
    return $r;
}

sub set {
    my $self = shift;
    my ($param, $val) = @_;
    my $isatty = shift || 0;
    $param = uc($param);
    carp "Invalid parameter ($param)" unless (length($param) == 4);
    $val = sprintf("%4s", $val);
    carp "Invalid value ($val)" unless (length($val) == 4);
    $self->_send($param, $val);
    while (1) {
	my $r = $self->_getResponse();
	croak "Undefined response" unless defined($r);
	if ($self->{_debug}) {
	    printf "D: Response: [%s]\n", join(', ', unpack('C*', $r));
	}
	if ($r eq 'WAIT') {
	    print "Please wait..." if $isatty;
	    next;
	}
	if ($r eq 'OK') {
	    return 1;
	} elsif ($r eq 'ERR') {
	    return 0;
	} else {
	    croak "Unknown response: ($r)";
	}
    }
}

1;
