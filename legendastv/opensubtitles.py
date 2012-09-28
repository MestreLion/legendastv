#!/usr/bin/python
# -*- coding: utf-8 -*-
#
#    Copyright (C) 2012 Rodrigo Silva (MestreLion) <linux@rodrigosilva.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program. See <http://www.gnu.org/licenses/gpl.html>
#
# Helper functions to wrap OpenSubtitles.org API

from __future__ import unicode_literals, absolute_import, division

import xmlrpclib
import struct, os, sys
import logging

log = logging.getLogger(__name__)

class OpenSubtitlesError(Exception):
    pass

def videohash(filename):

    block = 65536
    format = b"<%dQ" % (block//8) # unsigned long long little endian
    hash = os.path.getsize(filename) # initial value for hash is file size

    def partialhash(f):
        return sum(struct.unpack(format, f.read(block)))

    with open(filename, "rb") as f:
        try:
            hash += partialhash(f)
            f.seek(-block, os.SEEK_END)
            hash += partialhash(f)
            hash &= 0xFFFFFFFFFFFFFFFF # to remain as 64bit number
        except (IOError, struct.error):
            raise OpenSubtitlesError("File '%s' must be at least %d bytes" %
                                     (filename, block))
    return "%016x" % hash


def videoinfo(filename):
    osdb = xmlrpclib.ServerProxy('http://api.opensubtitles.org/xml-rpc')
    token = osdb.LogIn('','','',"Legendas.TV v0.1")

    if token['status'].startswith('200'):
        token = token['token']
    else:
        raise OpenSubtitlesError("Error accessing OpenSubtitles API: %s" %
                                 token['status'])

    hash = videohash(filename)
    result = osdb.CheckMovieHash2(token, [hash])
    return result['data'][hash] if result['data'] else []


if __name__ == "__main__":

    # scrap area, for tests

    # User selects a movie by filename...
    filename = (unicode(sys.argv[1], "utf-8")
                if len(sys.argv) > 1
                else os.path.expanduser("~/Videos/Revolution OS.avi"))
    try:
        for movie in videoinfo(filename):
            print movie
    except (OpenSubtitlesError, OSError) as e:
        print e