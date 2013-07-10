#!/bin/sh

lcdctrl=/usr/lib/digital-signage/lcdcontrol
pin=$1

# No OSD at startup
$lcdctrl set odsp 1
# startup with DVI input and keep it at that
$lcdctrl set finp 17
# Switch to cinema mode
$lcdctrl set wide 3
# Lock the menus, remote, control buttons, and power buttons
$lcdctrl set lmnu 1
$lcdctrl set lbtn 1
$lcdctrl set lrem 1
$lcdctrl set lpow 1
$lcdctrl set pset $pin
