#!/usr/bin/python
# -*- coding: utf-8 -*-
#
#    Copyright (C) 2012 Rodrigo Silva (MestreLion) <linux@rodrigosilva.com>
#    This file is part of Legendas.TV Subtitle Downloader
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
# Parser and utilities for Legendas.TV website

from __future__ import unicode_literals, absolute_import, division

import os
import re
import urllib
import urllib2
import urlparse
import operator
import logging
import json
import time
from lxml import html
from datetime import datetime

from .. import g, datatools as dt
from . import Provider

log = logging.getLogger(__name__)


# Search Type:
# <blank> - All subtitles
# d       - Destaque (Highlighted subtitles only)
# p       - Pack (Subtitle packs only, usually for series seasons)

def print_debug(text):
    log.debug('\n\t'.join(text.split('\n')))

class HttpBot(object):
    """ Base class for other handling basic http tasks like requesting a page,
        download a file and cache content. Not to be used directly
    """
    def __init__(self, base_url=""):
        self._opener = urllib2.build_opener(urllib2.HTTPCookieProcessor())
        scheme, netloc, path, q, f  = urlparse.urlsplit(base_url, "http")
        if not netloc:
            netloc, _, path = path.partition('/')
        self.base_url = urlparse.urlunsplit((scheme, netloc, path, q, f))

    def get(self, url, postdata=None):
        """ Send an HTTP request, either GET (if no postdata) or POST
            Keeps session and other cookies.
            postdata is a dict with name/value pairs
            url can be absolute or relative to base_url
        """
        url = urlparse.urljoin(self.base_url, url)
        if postdata:
            return self._opener.open(url, urllib.urlencode(postdata))
        else:
            return self._opener.open(url)

    def download(self, url, dir, filename=""):
        download = self.get(url)

        # If save name is not set, use the downloaded file name
        if not filename:
            filename = download.geturl()

        # Handle dir
        dir = os.path.expanduser(dir)
        if not os.path.isdir(dir):
            os.makedirs(dir)

        # Combine dir to convert filename to a full path
        filename = os.path.join(dir, os.path.basename(filename))

        with open(filename,'wb') as f:
            f.write(download.read())

        return filename

    def cache(self, url):
        filename = os.path.join(g.globals['cache_dir'], os.path.basename(url))
        if os.path.exists(filename):
            return True
        else:
            return (self.download(url, g.globals['cache_dir']))

    def quote(self, text):
        """ Quote a text for URL usage, similar to urllib.quote_plus.
            Handles unicode and also encodes "/"
        """
        if isinstance(text, unicode):
            text = text.encode('utf-8')
        return urllib.quote_plus(text, safe=b'')

    def parse(self, url, postdata=None):
        """ Parse an URL and return an etree ElementRoot.
            Assumes UTF-8 encoding
        """
        return html.parse(self.get(url, postdata),
                          parser=html.HTMLParser(encoding='utf-8'))

class LegendasTV(HttpBot, Provider):

    name = "Legendas.TV"
    url = "http://legendas.tv"

    _re_sub_language = re.compile(r"idioma/\w+_(\w+)\.")

    def __init__(self, login=None, password=None):
        super(LegendasTV, self).__init__(self.url)

        self.login    = login    or g.options['login']
        self.password = password or g.options['password']

        if not (self.login and self.password):
            return

        url = "/login"
        log.info("Logging into %s as %s", self.base_url + url, self.login)

        self.get(url, {'data[User][username]': self.login,
                       'data[User][password]': self.password})


    languages = dict(
        pb = dict(id= 1, code="brazil",  name="Português-BR"),
        en = dict(id= 2, code="usa",     name="Inglês"),
        es = dict(id= 3, code="es",      name="Espanhol"),
        fr = dict(id= 4, code="fr",      name="Francês"),
        de = dict(id= 5, code="de",      name="Alemão"),
        ja = dict(id= 6, code="japao",   name="Japonês"),
        da = dict(id= 7, code="denmark", name="Dinamarquês"),
        no = dict(id= 8, code="norway",  name="Norueguês"),
        sv = dict(id= 9, code="sweden",  name="Sueco"),
        pt = dict(id=10, code="pt",      name="Português-PT"),
        ar = dict(id=11, code="arabian", name="Árabe"),
        cs = dict(id=12, code="czech",   name="Checo"),
        zh = dict(id=13, code="china",   name="Chinês"),
        ko = dict(id=14, code="korean",  name="Coreano"),
        bg = dict(id=15, code="be",      name="Búlgaro"),
        it = dict(id=16, code="it",      name="Italiano"),
        pl = dict(id=17, code="poland",  name="Polonês"),
    )

    def getLanguages(self, language=None):
        # reading from cache
        cachefile = os.path.join(g.globals['cache_dir'],
                                 "languages_%s.json" % __name__.rpartition(".")[2])
        try:
            # cache must exist and be fresh (30 days)
            if os.path.getmtime(cachefile) > time.time() - 60*60*24*30:
                # be accessible and readable
                with open(cachefile) as f:
                    # be a valid json file
                    self.languages.update(json.load(f))
                    log.debug("loading languages from cache")
                    return self.languages
        except (OSError, IOError, ValueError, KeyError):
            pass

        # cache failed, retrieve from server
        url = "/busca?q=" + self.quote("'")
        tree = self.parse(url)

        log.debug("updating languages cache")
        for e in tree.xpath(".//select[@name='data[id_idioma]']/option"):
            id, name = int("0%s" % e.attrib['value']), e.text
            if id:
                for lang, value in dt.iter_find_in_dd(self.languages, 'id', id):
                    if not value['name'] == name:
                        log.debug("Updating language '%s' (%d): '%s' -> '%s'",
                                  lang, id, value['name'], name)
                        self.languages[lang].update({'name': name})
                    break
                else:
                    log.warn("Language not found: %d - '%s'", id, name)

        # save the cache
        try:
            with open(cachefile, 'w') as f:
                json.dump(self.languages, f, sort_keys=True, indent=2, separators=(',', ':'))
        except IOError:
            pass

        # return from json.load() to guarantee it will be identical as cache read
        return json.loads(json.dumps(self.languages))


    def getMovies(self, text):
        """ Given a search text, return a list of dicts with basic movie info:
            id, title, title_br, thumb (relative url for a thumbnail image)
        """
        movies = []

        tree = json.load(self.get("/util/busca_titulo/" + self.quote(text)))

        # [{u'Filme': {u'id_filme':    u'20389',
        #              u'dsc_nome':    u'Wu long tian shi zhao ji gui',
        #              u'dsc_nome_br': u'Kung Fu Zombie',
        #              u'dsc_imagen':  u'tt199148.jpg'}},]
        for e in tree:
            item = e['Filme']
            movie = dict(
                id       = int(item['id_filme']),
                title    = item['dsc_nome'],
                title_br = item['dsc_nome_br'],
                thumb    = item['dsc_imagen'],
            )
            if movie['thumb']:
                movie['thumb'] = "/img/poster/" + movie['thumb']
                if g.options['cache']:
                    self.cache(movie['thumb'])
            movies.append(movie)

        print_debug("Titles found for '%s':\n%s" % (text,
                                                    dt.print_dictlist(movies)))
        return movies


    """ Convenience wrappers for the main getSubtitles method """

    def getSubtitlesByMovie(self, movie, type=None, lang=None, allpages=True):
        return self.getSubtitles(movie_id=movie['id'],
                                 lang=lang, allpages=allpages)

    def getSubtitlesByMovieId(self, movie_id, type=None, lang=None, allpages=True):
        return self.getSubtitles(movie_id=movie_id,
                                 lang=lang, allpages=allpages)

    def getSubtitlesByText(self, text, type=None, lang=None, allpages=True):
        return self.getSubtitles(text=text, type=type,
                                 lang=lang, allpages=allpages)

    def getSubtitles(self, text="", type=None, lang=None, movie_id=None,
                       allpages=True):
        """ Main method for searching, parsing and retrieving subtitles info.
            Arguments:
            text - the text to search for
            type - The type of search that text refers to. An int as defined
                   in constans representing either Release, Title or User
            lang - The subtitle language to search for. An int as defined
                   in constants
            movie_id - search all subtitles from the specified movie. If used,
                       text and type (but not lang) are ignored
            Either text or movie_id must be provided
            Return a list of dictionaries with the subtitles found. Some info
            is related to the movie, not to that particular subtitle
        """
        if lang is None:
            lang = g.options['language']

        if   lang == "all": lang = ""
        elif lang == "pb" : lang = 1

        subtitles = []

        url = "/util/carrega_legendas_busca"
        if movie_id:  url += "/id_filme:"  + str(movie_id)
        else:         url += "/termo:"     + self.quote(text.strip())
        if type:      url += "/sel_tipo:"  + type
        if lang:      url += "/id_idioma:" + str(lang)

        page = 0
        lastpage = False
        while not lastpage:
            page += 1
            log.debug("loading %s", url)
            tree = self.parse(url)

            # <div class="">
            #     <span class="number number_2">35</span>
            #     <div class="f_left">
            #         <p><a href="/download/c0c4d6418a3474b2fb4e9dae3f797bd4/Gattaca/gattaca_dvdrip_divx61_ac3_sailfish">gattaca_dvdrip_divx61_ac3_(sailfish)</a></p>
            #         <p class="data">1210 downloads, nota 10, enviado por <a href="/usuario/SuperEly">SuperEly</a> em 02/11/2006 - 16:13 </p>
            #     </div>
            #     <img src="/img/idioma/icon_brazil.png" alt="Portugu&#234;s-BR" title="Portugu&#234;s-BR">
            # </div>
            for e in tree.xpath(".//article/div"):
                data = e.xpath(".//text()")
                dataurl = e.xpath(".//a")[0].attrib['href'].split('/')
                dataline = data[2].split(' ')
                sub = dict(
                    hash        = dataurl[2],
                    title       = dataurl[3],
                    downloads   = dataline[0],
                    rating      = dataline[3][:-1] or None,
                    date        = data[4].strip()[3:],
                    user_name   = data[3],
                    release     = data[1],
                    pack        = e.attrib['class'] == 'pack',
                    highlight   = e.attrib['class'] == 'destaque',
                    flag        = e.xpath("./img")[0].attrib['src']
                )
                dt.fields_to_int(sub, 'downloads', 'rating')
                sub['language'] = re.search(self._re_sub_language,
                                            sub['flag']).group(1)
                sub['date'] = datetime.strptime(sub['date'], '%d/%m/%Y - %H:%M')
                if sub['release'].startswith("(p)") and sub['pack']:
                    sub['release'] = sub['release'][3:]

                if g.options['cache']: self.cache(sub['flag'])
                subtitles.append(sub)

            # Page control
            if not allpages:
                lastpage = True
            else:
                next = tree.xpath("//a[@class='load_more']")
                if next:
                    url = next[0].attrib['href']
                else:
                    lastpage = True

        print_debug("Subtitles found for %s:\n%s" %
                   ( movie_id or "'%s'" % text, dt.print_dictlist(subtitles)))
        return subtitles


    def downloadSubtitle(self, hash, dir, basename=""):
        """ Download a subtitle archive based on subtitle id.
            Saves the archive as dir/basename, using the basename provided or,
            if empty, the one returned from the website.
            Return the filename (with full path) of the downloaded archive
        """
        print_debug("Downloading archive for subtitle '%s'" % hash)
        result = self.download('/downloadarquivo/' + hash, dir, basename)
        print_debug("Archive saved as '%s'" % (result))
        return result

    def rankSubtitles(self, movie, subtitles):
        """ Evaluates each subtitle based on wanted movie and give each a score.
            Return the list sorted by score, greatest first
        """

        def days(d):
            return (datetime.today() - d).days

        oldest = days(min([s['date'] for s in subtitles]))
        newest = days(max([s['date'] for s in subtitles]))

        for sub in subtitles:
            score = 0

            score += 10 * dt.get_similarity(dt.clean_string(movie['title']),
                                            dt.clean_string(sub['title']))
            score +=  3 * 1 if sub['highlight'] else 0
            score +=  5 * dt.get_similarity(movie['release'],
                                            dt.clean_string(sub['release']))
            score +=  1 * (sub['rating']/10 if sub['rating'] is not None else 0.8)
            score +=  1 * (1 - ( (days(sub['date'])-newest)/(oldest-newest)
                                 if oldest != newest
                                 else 0 ))

            sub['score'] = 10 * score / 20

        result = sorted(subtitles, key=operator.itemgetter('score'),
                        reverse=True)
        print_debug("Ranked subtitles for %s:\n%s" % (movie,
                                                      dt.print_dictlist(result)))
        return result
