#!/bin/sh
#
# Nautilus script for srtclean
#
# Copy or symlink to '~/.gnome2/nautilus-scripts', or to your system equivalent
#
# Copyright (C) 2011 Rodrigo Silva (MestreLion) <linux@rodrigosilva.com>
# License: GPLv3 or later, at your choice. See <http://www.gnu.org/licenses/gpl>

srtclean --recursive --convert UTF-8 --no-backup --in-place "$@" 2>&1 |
if type zenity >/dev/null 2>&1 ; then
	zenity --text-info --title "Clean Subtitles" \
		--no-wrap --width=1000 --height=500
else
	cat
fi
