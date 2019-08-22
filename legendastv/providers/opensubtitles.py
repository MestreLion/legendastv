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
import httplib
import struct
import os
import json
import time
import logging

log = logging.getLogger(__name__)

from .. import g, datatools as dt
from . import Provider
from ..utils import print_debug


class OpenSubtitlesError(Exception):
    pass


class Osdb(object):
    def __init__(self, username="", password="", language=""):
        self.osdb = xmlrpclib.ServerProxy('http://api.opensubtitles.org/xml-rpc')
        self.username = None
        self.language = None
        self.account  = None
        self.token    = None
        try:
            self.LogIn(username, password, language)
        except (xmlrpclib.Error, OpenSubtitlesError) as e:
            log.warn("Could not login to OSDB, some services may not work: %s", e)


    def LogIn(self, username="", password="", language=""):
        self.username = username
        self.language = language
        res = self._osdb_call(
            "LogIn",
            self.username,
            password,
            self.language,
            "Legendas.TV v%s" % g.globals['version']
        )
        self.token = res['token']
        self.account = res.get('data', None)


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
        nostatus = ('ServerInfo', 'GetSubLanguages')
        notoken  = nostatus + ('LogIn',)

        # Insert token as first argument for methods that require it
        if name not in notoken:
            if not self.token:
                raise OpenSubtitlesError("OSDB.%s requires logging in" % name)
            args = (self.token,) + args

        if name == 'LogIn' and args[1]:
            logargs = args[:1] + ('***',) + args[2:]  # hide password
        elif name not in notoken:
            logargs = ('***',) + args[1:]  # hide token
        else:
            logargs = args

        # Do the XML-RPC call
        try:
            timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(5)
            res = getattr(self.osdb, name)(*args)
        except (socket.error,
                httplib.ResponseNotReady,
                xmlrpclib.ProtocolError) as e:
            # most likely [Errno 110] Connection timed out
            raise OpenSubtitlesError("OSDB.%s%r: %s" % (name, logargs, e))
        finally:
            socket.setdefaulttimeout(timeout)

        if name == 'LogIn' and 'token' in res:
            logres = res.copy()
            logres['token'] = '***'
        else:
            logres = res


        log.debug("OSDB.%s%r -> %r", name, logargs, logres)

        # Check for result error status
        if name not in nostatus and not res.get('status', "").startswith("200"):
            raise OpenSubtitlesError("OpenSubtitles API Error in '%s': %s" %
                                     (name, res.get('status', "")))

        # Remove redundant or irrelevant data fields
        for k in ('status', 'seconds'):
            res.pop(k, None)

        # if remaining response has a single field named 'data',
        # return that field's value directly ("un-dict" the response)
        if len(res) == 1 and 'data' in res:
            return res['data']
        else:
            return res


    def __getattr__(self, name):
        return lambda *args: self._osdb_call(name, *args)




class OpenSubtitles(Osdb, Provider):
    name = "OpenSubtitles.org"
    url = "http://www.opensubtitles.org"

    def __init__(self, *args, **kwargs):
        super(OpenSubtitles, self).__init__(*args, **kwargs)
        self.auth = False


    def login(self, login, password):
        self.LogIn(login, password)
        self.auth = bool(self.account)
        return self.auth

    # https://www.opensubtitles.org/addons/export_languages.php
    # awk -F'\t' -v p="'" '/1\t1$/ {print p $2 p ": " p $1 p ",  # " $3}' | sort
    languages = {
        'ar': 'ara',  # Arabic
        'at': 'ast',  # Asturian
        'bg': 'bul',  # Bulgarian
        'br': 'bre',  # Breton
        'ca': 'cat',  # Catalan
        'cs': 'cze',  # Czech
        'da': 'dan',  # Danish
        'de': 'ger',  # German
        'el': 'ell',  # Greek
        'en': 'eng',  # English
        'eo': 'epo',  # Esperanto
        'es': 'spa',  # Spanish
        'et': 'est',  # Estonian
        'eu': 'baq',  # Basque
        'fa': 'per',  # Persian
        'fi': 'fin',  # Finnish
        'fr': 'fre',  # French
        'gl': 'glg',  # Galician
        'he': 'heb',  # Hebrew
        'hi': 'hin',  # Hindi
        'hr': 'hrv',  # Croatian
        'hu': 'hun',  # Hungarian
        'id': 'ind',  # Indonesian
        'is': 'ice',  # Icelandic
        'it': 'ita',  # Italian
        'ja': 'jpn',  # Japanese
        'ka': 'geo',  # Georgian
        'km': 'khm',  # Khmer
        'ko': 'kor',  # Korean
        'mk': 'mac',  # Macedonian
        'ms': 'may',  # Malay
        'nl': 'dut',  # Dutch
        'no': 'nor',  # Norwegian
        'oc': 'oci',  # Occitan
        'pb': 'pob',  # Portuguese (BR)
        'pl': 'pol',  # Polish
        'pt': 'por',  # Portuguese
        'ro': 'rum',  # Romanian
        'ru': 'rus',  # Russian
        'si': 'sin',  # Sinhalese
        'sk': 'slo',  # Slovak
        'sl': 'slv',  # Slovenian
        'sq': 'alb',  # Albanian
        'sr': 'scc',  # Serbian
        'sv': 'swe',  # Swedish
        'th': 'tha',  # Thai
        'tl': 'tgl',  # Tagalog
        'tr': 'tur',  # Turkish
        'uk': 'ukr',  # Ukrainian
        'vi': 'vie',  # Vietnamese
        'zh': 'chi',  # Chinese (simplified)
        'zt': 'zht',  # Chinese (traditional)
    }

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


    def getMovies(self, text):
        """ Given a search text, return a list of dicts with basic movie info:
            id, title, year, type
        """
        movies = []

        item = self.GuessMovieFromString([text])[text]
        if 'BestGuess' in item:
            item = item['BestGuess']
            mapping = dict(
                id       = "IDMovie",
                title    = "MovieName",
                year     = "MovieYear",
                type     = "MovieKind",
                season   = "SeriesSeason",
                episode  = "SeriesEpisode",
                imdb_id  = "IDMovieIMDB",
            )
        else:
            item = item['GuessIt']
            mapping = dict(
                id       = "",
                title    = "title",
                year     = "year",
                type     = "type",
                season   = "season",
                episode  = "episode",
                imdb_id  = "",
            )

        movies.append({k: item.get(v, None) for k, v in mapping.iteritems()})
        print_debug("Titles found for '{}':\n{}".format(
                        text, dt.print_dictlist(movies)))
        return movies


    """ Convenience wrappers for the main getSubtitles method """

    def getSubtitlesByMovie(self, movie, stype=None, lang=None):
        return self.getSubtitles(movie_id=movie['id'],
                                 stype=stype,
                                 lang=lang)

    def getSubtitlesByMovieId(self, movie_id, stype=None, lang=None):
        return self.getSubtitles(movie_id=movie_id,
                                 stype=stype,
                                 lang=lang)

    def getSubtitlesByText(self, text, stype=None, lang=None):
        return self.getSubtitles(text=text,
                                 stype=stype,
                                 lang=lang)

    def getSubtitles(self, text="", stype=None, lang=None, vinfo=None, vpath=None):  # @UnusedVariable
        """ Main method for searching, parsing and retrieving subtitles info.
            Arguments:
            text  - The text to search for
            stype - The type of subtitle. Either blank or a char as:
                     'p' - for subtitle pack (usually for a Series' whole Season)
                     'd' - destaque (highlighted subtitle, considered superior)
            lang  - The subtitle language to search for. An int as defined
                      in constants
            movie_id - search all subtitles from the specified movie. If used,
                       text and type (but not lang) are ignored
            Either text or movie_id must be provided
            Return a list of dictionaries with the subtitles found. Some info
            is related to the movie, not to that particular subtitle
        """
        subtitles = []
        subs = []  # @UnusedVariable

        if lang is None:
            lang = g.options['language'] or ""

        # Re-map 2-digit to 3-digit language code
        lang = ','.join(self.languages.get(_, _) for _ in lang.split(','))

        if vpath and not vinfo:
            vinfo = videoinfo(vpath, self)

        if vpath:
#         for title in vinfo or []:
#             subs.extend(self.SearchSubtitles([{
#                 'sublanguageid': lang,
#                 'moviehash':     title['hash'],
#                 'moviebytesize': title['size'],
#             }]))
#             subs.extend(self.SearchSubtitles([{
#                 'sublanguageid': lang,
#                 'imdbid':        title['MovieImdbID'],
#                 'season':        title['SeriesSeason'],
#                 'episode':       title['SeriesEpisode'],
#             }]))
#             subs.extend(self.SearchSubtitles([{
#                 'sublanguageid': lang,
#                 'query':         text or title['MovieName'],
#                 'tag':           os.path.basename(vpath or '') or None,
#             }]))
            for sub in self.SearchSubtitles([{
                'sublanguageid': lang,
                'tag':           os.path.basename(vpath or '') or None,
            }]):

#                 sub = dict(
#                     hash        = dataurl[2],
#                     title       = dataurl[3],
#                     downloads   = dataline[0],
#                     rating      = dataline[3][:-1] or None,
#                     date        = data[4].strip()[3:],
#                     user_name   = data[3],
#                     release     = data[1],
#                     pack        = e.attrib['class'] == 'pack',
#                     highlight   = e.attrib['class'] == 'destaque',
#                     flag        = e.xpath("./img")[0].attrib['src']
#                 )
#                 dt.fields_to_int(sub, 'downloads', 'rating')
#                 sub['language'] = languages.get(re.search(self._re_sub_language,
#                                                           sub['flag']).group(1))
#                 sub['date'] = datetime.strptime(sub['date'], '%d/%m/%Y - %H:%M')
#                 if sub['release'].startswith("(p)") and sub['pack']:
#                     sub['release'] = sub['release'][3:]

                subtitles.append(sub)

#         if text:
#             subtitles.extend()

        return subtitles




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
            # Inject video hash and byte size into result
            for r in result:
                r['hash'] = vhash
                r['size'] = os.path.getsize(filename)
    except OpenSubtitlesError as e:
        log.error(e)

    return result
