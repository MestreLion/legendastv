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
import socket
import struct
import os
import json
import time
import logging

log = logging.getLogger(__name__)

from .. import g
from . import Provider


class OpenSubtitlesError(Exception):
    pass


class Osdb(object):
    def __init__(self, username="", password="", language=""):
        self.osdb = xmlrpclib.ServerProxy('http://api.opensubtitles.org/xml-rpc')
        self.username = None
        self.language = None
        self.token = None
        try:
            self.LogIn(username, password, language)
        except (xmlrpclib.Error, OpenSubtitlesError) as e:
            log.warn("Could not login to OSDB, some services may not work: %s", e)


    def LogIn(self, username="", password="", language=""):
        self.username = username
        self.language = language
        self.token = self._osdb_call("LogIn",
                                     self.username,
                                     password,
                                     self.language,
                                     "Legendas.TV v%s" % g.globals['version'])


    def LogOut(self):
        if self.token:
            self._osdb_call("LogOut")
            self.token = None


    def GetSubLanguages(self, language=None):
        if language is None:
            language = self.language
        return self._osdb_call("GetSubLanguages", language)


    def __enter__(self):
        return self

    def __exit__(self, *args):  #@UnusedVariable
        self.LogOut()


    def _osdb_call(self, name, *args):
        # Insert token as first argument for methods that require it
        if name not in ['ServerInfo', 'LogIn', 'GetSubLanguages']:
            if not self.token:
                raise OpenSubtitlesError("OSDB.%s requires logging in" % name)
            args = (self.token,) + args

        # Do the XML-RPC call
        try:
            timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(5)
            raise socket.error(110, 'Connection timed out')
            res = getattr(self.osdb, name)(*args)
        except socket.error as e:
            # most likely [Errno 110] Connection timed out
            raise OpenSubtitlesError(e)
        finally:
            socket.setdefaulttimeout(timeout)

        log.debug("OSDB.%s%r -> %r",
                  name,
                  args[:1] + ('***',) + args[2:] if name == "LogIn" else args,
                  res)

        # Check for result error status
        if not res.get('status', "").startswith("200"):
            raise OpenSubtitlesError("OpenSubtitles API Error in '%s': %s" %
                                     (name, res.get('status', "")))

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




class OpenSubtitles(Osdb, Provider):
    name = "OpenSubtitles.org"
    url = "http://www.opensubtitles.org"

    def __init__(self, *args, **kwargs):
        super(OpenSubtitles, self).__init__(*args, **kwargs)


    def getLanguages(self, language="en"):
        # reading from cache
        cache = {}
        cachefile = os.path.join(g.globals['cache_dir'],
                                 "languages_%s.json" %
                                    __name__.rpartition(".")[2])
        try:
            # cache must exist and be fresh (30 days)
            if os.path.getmtime(cachefile) > time.time() - 60*60*24*30:
                # be accessible and readable
                with open(cachefile) as f:
                    # be a valid json file
                    cache = json.load(f)
                    # and must contain the specified language
                    languages = cache[language]
                    log.debug("loading languages from cache")
                    return languages
        except (OSError, IOError, ValueError, KeyError):
            pass

        # cache failed, retrieve from server
        langs = self.GetSubLanguages(language)

        log.debug("updating languages cache")
        languages = {}
        for lang in langs:
            if lang['ISO639']:
                languages.update({lang['ISO639']:{'id'  : lang['SubLanguageID'],
                                                  'name': lang['LanguageName']}})

        # save the cache
        try:
            with open(cachefile, 'w') as f:
                # update the cache with retrieved language data
                cache.update({language: languages})
                json.dump(cache, f, sort_keys=True, indent=2, separators=(',', ':'))
        except IOError:
            pass

        # return from json.load() to guarantee it will be identical as cache read
        return json.loads(json.dumps(languages))




def videohash(filename):

    block = 65536
    fmt = b"<%dQ" % (block//8) # unsigned long long little endian
    vhash = os.path.getsize(filename) # initial value for hash is file size

    def partialhash(f):
        return sum(struct.unpack(fmt, f.read(block)))

    with open(filename, "rb") as f:
        try:
            vhash += partialhash(f)
            f.seek(-block, os.SEEK_END)
            vhash += partialhash(f)
            vhash &= 0xFFFFFFFFFFFFFFFF # to remain as 64bit number
        except (IOError, struct.error):
            raise OpenSubtitlesError("File '%s' must be at least %d bytes" %
                                     (filename, block))
    return b"%016x" % vhash


def videoinfo(filename, osdb=None):
    result = []
    if osdb is None:
        osdb = Osdb()
    try:
        vhash = videohash(filename)
        result = osdb.CheckMovieHash2([vhash])
        if result:
            try:
                result = result[vhash]
            except TypeError:
                # OSDB returned a list instead of a dictionary, Lord knows why
                log.warn("OSDB returned a list for hash '%s'", hash)
                result = result[0]
    except OpenSubtitlesError as e:
        log.error(e)

    return result
