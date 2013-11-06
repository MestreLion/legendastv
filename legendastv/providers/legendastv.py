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
from lxml import html
from datetime import datetime

from .. import g, datatools as dt
from . import Provider

log = logging.getLogger(__name__)


# Languages [and flag names (language "codes")]:
#  1 - Português-BR (Brazilian Portuguese) [brazil]
#  2 - Inglês (English) [usa]
#  3 - Espanhol (Spanish) [es]
#  4 - Francês (French) [fr]
#  5 - Alemão (German) [de]
#  6 - Japonês (Japanese) [japao]
#  7 - Dinamarquês (Danish) [denmark]
#  8 - Norueguês (Norwegian) [norway]
#  9 - Sueco (Swedish) [sweden]
# 10 - Português-PT (Iberian Portuguese) [pt]
# 11 - Árabe (Arabic) [arabian]
# 12 - Checo (Czech) [czech]
# 13 - Chinês (Chinese) [china]
# 14 - Coreano (Corean) [korean]
# 15 - Búlgaro (Bulgarian) [be]
# 16 - Italiano (Italian) [it]
# 17 - Polonês (Polish) [poland]

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

    def _searchdata(self, text, type=None, lang=None):
        """ Helper for the website's search form. Return a dict suitable for
            the get() method
        """
        return {'txtLegenda': text,
                'selTipo'   : type or 1, # Release search
                'int_idioma': lang or 1, # Brazilian Portuguese
                'btn_buscar.x': 0,
                'btn_buscar.y': 0,}

    _re_movie_text = re.compile(r"^(?P<title>.+)\ \((?P<year>\d+)\)$")

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

    def getMovieDetails(self, movie):
        return self.getMovieDetailsById(movie['id'])

    def getMovieDetailsById(self, id):
        """ Returns a dict with additional info about a movie than the ones
            provided by getMovies(), such as:
            title_br - movie title in Brazil
            genre - dict with id, genre, genre_br as defined in constants
            synopsis - a (usually lame) synopsis of the movie
        """
        url = "index.php?opcao=buscarlegenda&filme=" + str(id)
        tree = html.parse(self.get(url, self._searchdata("..")))

        #<table width="95%" border="0" cellpadding="0" cellspacing="0" bgcolor="#f2f2f2" class="filmresult">
        #<tr>
        #    <td width="115" rowspan="4" valign="top"><div align="center"><img src="thumbs/1802-87eb3781511594f8ea4123201df05f36.jpg" /></div></td>
        #    <td width="335"><div align="left"><strong>T&iacute;tulo:</strong>
        #      CSI: Miami - 1st Season
        #      <strong>(
        #      2002              )              </strong></div></td>
        #</tr>
        #<tr>
        #    <td><div align="left"><strong>Nacional:</strong>
        #      CSI: Miami - 1&ordf; Temporada            </div></td>
        #</tr>
        #<tr>
        #    <td><strong>G&ecirc;nero:</strong>              Seriado</td>
        #</tr>
        #<tr>
        #    <td><div align="left"><strong>Sinopse:</strong>
        #      Mostra o trabalho da equipe de investigadores do sul da Fl&oacute;rida que soluciona crimes atrav&eacute;s da mistura de m&eacute;todos cient&iacute;ficos, t&eacute;cnicas tradicionais, tecnologia de ponta e instinto apurado para descobrir pistas.(mais)
        #    </div></td>
        #</tr>
        #</table>
        e = tree.xpath(".//table[@class='filmresult']")[-1]
        data = e.xpath(".//text()")
        movie = dict(
            id          = id,
            title       = data[ 2].strip(),
            year        = data[ 3],
            title_br    = data[ 6].strip(),
            genre       = data[ 9].strip(),
            synopsis    = data[12].strip(),
            thumb       = e.xpath(".//img")[0].attrib['src']
        )
        movie['year'] = int(dt.clean_string(movie['year']))

        print_debug("Details for title %s: %s" % (id, movie))
        return movie

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

    _re_sub_language = re.compile(r"idioma/\w+_(\w+)\.")
    _re_sub_text = re.compile(r"""gpop\(.*
        #'(?P<title>.*)',
        #'(?P<title_br>.*)',
        '(?P<release>.*)',
        '(?P<cds>.*)',
        '(?P<fps>.*)',
        '(?P<size>\d+)MB',
        '(?P<downloads>.*)',.*
        src=\\'(?P<flag>[^']+)\\'.*,
        '(?P<date>.*)'\)\).*
        abredown\('(?P<hash>\w+)'\).*
        abreinfousuario\((?P<user_id>\d+)\)""",
        re.VERBOSE + re.DOTALL)

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
            #     <img src="/img/idioma/icon_brazil.png" alt="Portugu&#195;&#170;s-BR" title="Portugu&#195;&#170;s-BR">
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

    def getSubtitleDetails(self, hash):
        """ Returns a dict with additional info about a subtitle than the ones
            provided by getSubtitles(), such as:
            imdb_url, description (html), updates (list), votes
            As with getSubtitles(), some info are related to the movie, not to
            that particular subtitle
        """
        sub = {}
        tree = html.parse(self.get('info.php?d=' + hash))

        sub['imdb_url'] = tree.xpath("//a[@class='titulofilme']")
        if len(sub['imdb_url']):
            sub['imdb_url'] = sub['imdb_url'][0].attrib['href']

        sub['synopsis'] = " ".join(
            [t.strip() for t in tree.xpath("//span[@class='sinopse']//text()")])

        sub['description'] = tree.xpath("//div[@id='descricao']")
        if sub['description']:
            sub['description'] = sub['description'][0].text + \
                                 "".join([html.tostring(l)
                                          for l in sub['description'][0]]) + \
                                 sub['description'][0].tail.strip()

        def info_from_list(datalist, text):
            return "".join([d for d in datalist
                            if d.strip().startswith(text)]
                           ).split(text)[-1].strip()

        data = [t.strip() for t in tree.xpath("//table//text()") if t.strip()]
        sub.update(re.search(self._re_movie_text, data[0]).groupdict())
        sub.update(dict(
            title       = data[data.index("Título Original:") + 1],
            title_br    = data[data.index("Título Nacional:") + 1],
            release     = data[data.index("Rls:") + 1],
            language    = data[data.index("Idioma:") + 1],
            fps         = data[data.index("FPS:") + 1],
            cds         = data[data.index("CDs:") + 1],
            size        = data[data.index("Tamanho:") + 1][:-2],
            downloads   = data[data.index("Downloads:") + 1],
            comments    = data[data.index("Comentários:") + 1],
            rating      = info_from_list(data, "Nota:").split("/")[0].strip(),
            votes       = info_from_list(data, "Votos:"),
            user_name   = info_from_list(data, "Enviada por:"),
            date        = info_from_list(data, "Em:"),
            id          = info_from_list(data, "idl =")[:-1],
        ))
        sub['date'] = datetime.strptime(sub['date'], '%d/%m/%Y - %H:%M')

        dt.fields_to_int(sub, 'id', 'year', 'downloads', 'comments', 'cds', 'fps',
                           'size', 'votes')

        print_debug("Details for subtitle '%s': %s" % (hash, sub))
        return sub

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
