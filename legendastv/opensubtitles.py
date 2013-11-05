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

from __future__ import unicode_literals

import xmlrpclib
import struct, os
import logging

log = logging.getLogger(__name__)

import g


class OpenSubtitlesError(Exception):
    pass


class Osdb(object):
    def __init__(self, username="", password="", language=""):
        self.osdb = xmlrpclib.ServerProxy('http://api.opensubtitles.org/xml-rpc')
        self.LogIn(username, password, language)


    def LogIn(self, username="", password="", language=""):
        self.username = username
        self.language = language
        self.token = self._osdb_call("LogIn", self.username, password, self.language,
                                     "Legendas.TV v%s" % g.globals['version'])


    def LogOut(self):
        if self.token:
            self._osdb_call("LogOut")
            self.token = None


    def __enter__(self): return self
    def __exit__(self, *args): self.LogOut()
    def __del__(self): self.LogOut()


    def _osdb_call(self, name, *args):
        # Insert token as first argument for methods that require it
        if name not in ['ServerInfo', 'LogIn', 'GetSubLanguages']:
            args = (self.token,) + args

        # Do the XML-RPC call
        res = getattr(self.osdb, name)(*args)
        log.debug("OSDB.%s%r -> %r",
                  name, args[:1] + ('***',) + args[2:] if name == "LogIn" else args, res)

        # Check for result error status
        if res.has_key('status') and not res['status'].startswith("200"):
            raise OpenSubtitlesError("OpenSubtitles API Error in '%s': %s" %
                                     (name, res['status']))

        # Remove redundant or irrelevant data fields
        for k in ['status', 'seconds']:
            res.pop(k, None)

        # if remaining response has a single field (most likely 'data'),
        # return that field's value directly ("un-dict" the response)
        if len(res) == 1:
            return res.popitem()[1]
        else:
            return res


    def __getattr__(self, name):
        return lambda *args: self._osdb_call(name, *args)




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
    return b"%016x" % hash


def videoinfo(filename, osdb=None):
    if osdb is None:
        osdb = Osdb()
    hash = videohash(filename)
    result = osdb.CheckMovieHash2([hash])
    return result[hash] if result else []




if __name__ == "__main__":

    import sys, os.path as osp

    logging.basicConfig(level=logging.DEBUG)

    try:
        osdb = Osdb()
        osdb.ServerInfo()
        osdb.GetSubLanguages('pb')

        for path in sys.argv[1:]:
            if osp.isfile(path):
                print
                print path
                print videohash(path)
                for movie in videoinfo(path, osdb):
                    print movie
                    videoinfo(path, osdb)
    except OpenSubtitlesError as e:
        log.error(e)
