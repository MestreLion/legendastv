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
from ..utils import notify, print_debug

log = logging.getLogger(__name__)


# Search Type:
# <blank> - All subtitles
# d       - Destaque (Highlighted subtitles only)
# p       - Pack (Subtitle packs only, usually for series seasons)

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

    def download(self, url, savedir, filename="", overwrite=True):
        download = self.get(url)

        # If save name is not set, use the downloaded file name
        if not filename:
            filename = download.geturl().rstrip("/")

        # Handle dir
        savedir = os.path.expanduser(savedir)
        if not os.path.isdir(savedir):
            os.makedirs(savedir)

        # Combine dir to convert filename to a full path
        filename = os.path.join(savedir, os.path.basename(filename))

        if overwrite or not os.path.isfile(filename):
            with open(filename,'wb') as f:
                f.write(download.read())
        else:
            log.debug("Using cached file")

        return filename

    def cache(self, url, subdir=""):
        filename = os.path.join(g.globals['cache_dir'], subdir, os.path.basename(url))
        if os.path.exists(filename):
            return True
        else:
            return (self.download(url, os.path.join(g.globals['cache_dir'], subdir)))

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

    def __init__(self):
        super(LegendasTV, self).__init__(self.url)
        self.auth = False

    def login(self, login, password):
        if not (login and password):
            return

        url = "/login"
        log.info("Logging in %s as %s", self.base_url + url, login)

        try:
            response = self.get(url, {'data[User][username]': login,
                                      'data[User][password]': password})
        except (urllib2.HTTPError, urllib2.URLError) as e:
            if (getattr(e, 'code', 0) in (513,  # Service Unavailable
                                          )
                or any(str(errno) in e.reason
                       for errno in (111,       # Connection refused
                                     ))) or True:
                log.error(e)
                raise g.LegendasError("Legendas.TV website is down!")
            else:
                raise

        # Check login: url redirect and logout link available
        self.auth = (not response.geturl().endswith(url)
                     and b'href="/users/logout"' in response.read())
        return self.auth

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

    def getLanguages(self, language=None):  # @UnusedVariable
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
            langid, name = int("0%s" % e.attrib['value']), e.text
            if langid:
                for lang, value in dt.iter_find_in_dd(self.languages,
                                                      'id', langid):
                    if not value['name'] == name:
                        log.debug("Updating language '%s' (%d): '%s' -> '%s'",
                                  lang, langid, value['name'], name)
                        self.languages[lang].update({'name': name})
                    break
                else:
                    log.warn("Language not found: %d - '%s'", langid, name)

        # save the cache
        try:
            with open(cachefile, 'w') as f:
                json.dump(self.languages, f, sort_keys=True, indent=2,
                          separators=(',', ':'))
        except IOError:
            pass

        # return from json.load() to guarantee it will be identical as cache read
        return json.loads(json.dumps(self.languages))


    def getMovies(self, text):
        """ Given a search text, return a list of dicts with basic movie info:
            id, title, title_br, thumb (relative url for a thumbnail image)
        """
        movies = []

        searchtext = text
        #searchtext = searchtext.replace("'", "\\'")
        searchtext = searchtext.replace(":", " ")
        url = "/legenda/sugestao/" + self.quote(searchtext.strip())
        log.debug("loading %s", url)
        try:
            tree = json.load(self.get(url))
        except (urllib2.HTTPError, urllib2.httplib.BadStatusLine) as e:
            notify("Server error retrieving URL!")
            log.error(e)
            tree = []

        # [{"_index":"filmes","_type":"filme","_id":"772","_score":null,
        #   "_source":{"id_filme":"772",
        #              "id_imdb":"119177",
        #              "tipo":"M",
        #              "int_genero":"1001",
        #              "dsc_imagen":"tt119177.jpg",
        #              "dsc_nome":"Gattaca",
        #              "dsc_sinopse":"Num futuro...\r\n",
        #              "dsc_data_lancamento":"1997",
        #              "dsc_url_imdb":null,
        #              "dsc_nome_br":"Gattaca",
        #              "soundex":"KTK",
        #              "temporada":null,
        #              "id_usuario":null,
        #              "flg_liberado":"1",
        #              "dsc_data_liberacao":null,
        #              "dsc_data":null,
        #              "dsc_metaphone_us":"KTK",
        #              "dsc_metaphone_br":"KTK",
        #              "episodios":null,
        #              "flg_seriado":null,
        #              "last_used":"1373179590",
        #              "deleted":false},
        #   "sort":[null]}]

        # [{"_index":"filmes","_type":"filme","_id":"36483","_score":None,
        #   "_source":{"id_filme":"36483",
        #              "id_imdb":"2306299",
        #              "tipo":"S",
        #              "int_genero":"0",
        #              "dsc_imagen":"legendas_tv_20150208120453.jpg",
        #              "dsc_nome":"Vikings",
        #              "dsc_sinopse":"A s\u00e9rie apresenta a trajet\u00f3ria...",
        #              "dsc_data_lancamento":"2015",
        #              "dsc_url_imdb":"http:\/\/www.imdb.com\/title\/tt2306299\/",
        #              "dsc_nome_br":"Vikings - 3\u00aa Temporada",
        #              "soundex":None,
        #              "temporada":"3",
        #              "id_usuario":"2262943",
        #              "flg_liberado":"0",
        #              "dsc_data_liberacao":None,
        #              "dsc_data":"2015-02-08T12:05:19",
        #              "dsc_metaphone_us":None,
        #              "dsc_metaphone_br":None,
        #              "episodios":None,
        #              "flg_seriado":None,
        #              "last_used":"0",
        #              "deleted":False},
        #   "sort":["3"]},]

        mapping = dict(
            id       = "id_filme",
            title    = "dsc_nome",
            title_br = "dsc_nome_br",
            thumb    = "dsc_imagen",
            year     = "dsc_data_lancamento",
            type     = "tipo",
            season   = "temporada",
            imdb_id  = "id_imdb",
        )

        typemap = {
            'M': 'movie',
            'S': 'episode',
        }

        for e in tree:
            item = e['_source']
            movie = {k: item.get(v, None) for k, v in mapping.iteritems()}

            if movie.get('thumb', None):
                movie['thumb'] = "http://i.legendas.tv/poster/" + movie['thumb']
                if g.options['cache']:
                    self.cache(movie['thumb'], 'thumbs')

            if movie.get('type', None):
                movie['type'] = typemap.get(movie['type'], None)

            movies.append(movie)

        print_debug("Titles found for '%s':\n%s" % (text,
                                                    dt.print_dictlist(movies)))
        return movies


    """ Convenience wrappers for the main getSubtitles method """

    def getSubtitlesByMovie(self, movie, stype=None, lang=None, allpages=True):
        return self.getSubtitles(movie_id=movie['id'],
                                 stype=stype,
                                 lang=lang,
                                 allpages=allpages)

    def getSubtitlesByMovieId(self, movie_id, stype=None, lang=None, allpages=True):
        return self.getSubtitles(movie_id=movie_id,
                                 stype=stype,
                                 lang=lang,
                                 allpages=allpages)

    def getSubtitlesByText(self, text, stype=None, lang=None, allpages=True):
        return self.getSubtitles(text=text,
                                 stype=stype,
                                 lang=lang,
                                 allpages=allpages)

    def getSubtitles(self, text="", stype=None, lang=None, movie_id=None,
                       allpages=True):
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
        if lang is None:
            lang = g.options['language'] or ""

        # Convert 2-char language ISO code to lang_id used in search
        lang_id = self.languages.get(lang, {}).get('id', 0)

        # "re-map" languages to a format useful for fast subtitle processing
        languages = {}
        for lang_iso, language in self.languages.iteritems():
            languages[language['code']] = lang_iso

        subtitles = []

        url = "/util/carrega_legendas_busca"
        if movie_id:  url += "_filme/"     + str(movie_id)
        else:         url += "/"           + self.quote(text.strip())

        if lang:
            url += "/" + str(lang_id)
        else:
            url += "/-"

        if stype:
            url += "/" + stype

        page = 0
        lastpage = False
        while not lastpage:
            page += 1
            log.debug("loading %s", url)
            try:
                tree = self.parse(url)
            except (urllib2.HTTPError, urllib2.httplib.BadStatusLine) as e:
                notify("Server error retrieving URL!")
                log.error(e)
                break

            # <div class="">
            #     <span class="number number_2">35</span>
            #     <div class="f_left">
            #         <p><a href="/download/c0c4d6418a3474b2fb4e9dae3f797bd4/Gattaca/gattaca_dvdrip_divx61_ac3_sailfish">gattaca_dvdrip_divx61_ac3_(sailfish)</a></p>
            #         <p class="data">1210 downloads, nota 10, enviado por <a href="/usuario/SuperEly">SuperEly</a> em 02/11/2006 - 16:13 </p>
            #     </div>
            #     <img src="/img/idioma/icon_brazil.png" alt="Portugu&#234;s-BR" title="Portugu&#234;s-BR">
            # </div>
            for e in tree.xpath(".//article/div"):
                if e.attrib['class'].startswith('banner'): continue
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
                sub['language'] = languages.get(re.search(self._re_sub_language,
                                                          sub['flag']).group(1))
                sub['date'] = datetime.strptime(sub['date'], '%d/%m/%Y - %H:%M')
                if sub['release'].startswith("(p)") and sub['pack']:
                    sub['release'] = sub['release'][3:]

                if g.options['cache']: self.cache(sub['flag'])
                subtitles.append(sub)

            # Page control
            if not allpages:
                lastpage = True
            else:
                nextpage = tree.xpath("//a[@class='load_more']")
                if nextpage:
                    url = nextpage[0].attrib['href']
                else:
                    lastpage = True

        print_debug("Subtitles found for %s:\n%s" %
                   ( movie_id or "'%s'" % text, dt.print_dictlist(subtitles)))
        return subtitles


    def downloadSubtitle(self, filehash, savedir, basename="", overwrite=True):
        """ Download a subtitle archive based on subtitle id.
            Saves the archive as dir/basename, using the basename provided or,
            if empty, the one returned from the website.
            Return the filename (with full path) of the downloaded archive
        """
        if not self.auth:
            log.warn("Subtitle download requires user to be logged in")

        url = '/downloadarquivo/%s' % filehash
        print_debug("Downloading archive for subtitle from %s" % url)

        try:
            result = self.download(url, savedir, basename, overwrite=overwrite)
        except (urllib2.HTTPError, urllib2.httplib.BadStatusLine) as e:
            log.error(e)
            return

        print_debug("Archive saved as '%s'" % (result))
        return result

    def rankSubtitles(self, movie, subtitles):
        """ Evaluates each subtitle based on wanted movie and give each a score.
            Return the list sorted by score, greatest first
        """

        if not subtitles:
            return

        def days(d):
            return (datetime.today() - d).days

        oldest = days(min([s['date'] for s in subtitles]))
        newest = days(max([s['date'] for s in subtitles]))

        for sub in subtitles:
            sub['similarity'] = dt.get_similarity(movie['release'],
                                                  dt.clean_string(sub['release']))

            score = 0

            score += 20 * dt.get_similarity(dt.clean_string(movie['title']),
                                            dt.clean_string(sub['title']))
            score += 12 * sub['similarity']
            score +=  3 * 1 if sub['highlight'] else 0
            score +=  2 * 1 if sub['pack'] else 0
            score +=  2 * (sub['rating']/10
                           if sub['rating'] is not None
                           else 0.8)
            score +=  1 * (1 - ( (days(sub['date'])-newest)/(oldest-newest)
                                 if (oldest - newest) > 90
                                 else 0 ))

            sub['score'] = 10 * score / 40

        result = sorted(subtitles, key=operator.itemgetter('score'),
                        reverse=True)
        print_debug("Ranked subtitles for %s:\n%s" % (movie,
                                                      dt.print_dictlist(result)))
        return result


    def _matching_points(self, ref, val, p):
        if not ref:
            if not val: return p[0]  # no reference and no value
            else:       return p[1]  # no reference, but at least has value
        if not val:     return p[2]  # reference available, but no value
        if val != ref:  return p[3]  # value different than reference
        else:           return p[4]  # value matches reference


    def rankMovies(self, movie, movies):
        year = movie.get('year', None)
        title = dt.clean_string(movie['title'])
        mtype = 'movie'
        points = dict(
            year  = (0, 1, -1, -3, 5),
            type  = (0, 0, -1, -5, 1),
            title = (8, 0)
        )
        max_score = sum((max(w) for w in points.itervalues()))
        min_score = sum((min(w) for w in points.itervalues()))

        for m in movies:
            y = m.get('year', None)
            t = m.get('type', None)
            s = dt.get_similarity(title, dt.clean_string(m['title']))

            score = 0
            score += self._matching_points(year,  y, points['year'])
            score += self._matching_points(mtype, t, points['type'])
            score += s * points['title'][0]

            m['score'] = 10.0 * (score - min_score) / (max_score - min_score)
            m['similarity'] = s

        result = sorted(movies,
                        key=operator.itemgetter('score'),
                        reverse=True)

        print_debug("Ranked movies for %s:\n%s" %
                    (movie,
                     dt.print_dictlist(result)))

        return result


    def rankSeries(self, episode, seasons):  # @UnusedVariable
        return seasons

    def rankTitles(self, title, titles):
        if title.get('type') == 'episode':
            ranker = self.rankSeries
        else:
            ranker = self.rankMovies
        return ranker(title, titles)
