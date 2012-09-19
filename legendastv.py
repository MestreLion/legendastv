#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# legendas - an API for Legendas.TV movie/TV series subtitles website
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
# When used as a module, provides several methods to log in, search for movies
# and subtitles, retrieve their data, and download and extract the subtitles.
#
# When used as a script, uses command-line parameters to log in, search for
# a title (or torrent "release"), download, extract and rename the most suitable
# subtitle

# TODO: (the loooong Roadmap list):
# - more robust (ok, *any*) error handling.
# - log debug messages to file instead of output to console
# - convert magic numbers to enums / named constants
# - create decent classes for entities (movies, subtitles, comments)
# - cache movies and subtitles info to prickle/database
# - re-estructure the methods into html-parsing (private) and task-driven ones
#   a method for parsing each website page to feed the class/database, used by
#   the user-oriented "getXxxByXxx()" methods to retrieve and present the data
# - Console interactive mode to simulate current website navigation workflow:
#   search movie > select movie in list > select subtitle in list > download >
#   extract > handle files
# - Gtk GUI for interactive mode
# - Research Filebot, FlexGet, and others, to see what interface is expected for
#   a subtitle plugin
# - Make a Windows/OSX port possible: cache and config dirs, unrar lib
# - Create a suitable workflow for TV Series (seasons, episodes)

import os
import re
import sys
import dbus
import urllib
import urllib2
from lxml import html
from datetime import datetime
import difflib
import rarfile
import zipfile
import ConfigParser
import operator

_globals = {
    'appname'   : "legendastv",
    'apptitle'  : "Legendas.TV",
    'appicon'   : os.path.join(os.path.dirname(os.path.realpath(__file__)),
                               "icon.png"),
    'notifier'  : None,
}
_globals.update({
    'cache_dir' : os.path.join(os.environ.get('XDG_CACHE_HOME') or
                               os.path.join(os.path.expanduser('~'), '.cache'),
                               _globals['appname']),
    'config_dir': os.path.join(os.environ.get('XDG_CONFIG_HOME') or
                               os.path.join(os.path.expanduser('~'), '.config'),
                               _globals['appname']),
    'notify_icon': _globals['appicon']
})

# These factory settings are also available at config file
login      = ""
password   = ""
debug      = True
cache      = True
similarity = 0.7
notifications = True


# Languages [and flag names (language "codes")]:
#  1 * Português-BR (Brazilian Portuguese) [br]
#  2 * Inglês (English) [us]
#  3 * Espanhol (Spanish) [es]
#  4 - Francês (French) [fr]
#  5 - Alemão (German) [de]
#  6 - Japonês (Japanese) [japao]
#  7 - Dinamarquês (Danish) [denmark]
#  8 - Norueguês (Norwegian) [norway]
#  9 - Sueco (Swedish) [sweden]
# 10 * Português-PT (Iberian Portuguese) [pt]
# 11 - Árabe (Arabic) [arabian]
# 12 - Checo (Czech) [czech]
# 13 - Chinês (Chinese) [china]
# 14 - Coreano (Corean) [korean]
# 15 - Búlgaro (Bulgarian) [be]
# 16 - Italiano (Italian) [it]
# 17 - Polonês (Polish) [poland]

# In search form, only languages marked with "*" are available.
# Search extra options are:
#100 - Others (the ones not marked with "*")
# 99 - All

# Search Type:
# 1 - Release (movie "release", usually the torrent/file title)
# 2 - Filme (movie title, searches for both original and translated title)
# 3 - Usuario (subtitle uploader username)


# CDs: 0, 1, 2, 3, 4, 5
# FPS: 0, 23, 24, 25, 29, 60

# Genre:
# 15 - Ação
# 16 - Animação
# 17 - Aventura
# 34 - Clássico
# 14 - Comédia
# 32 - Desenho Animado
# 28 - Documentário
# 30 - Drama
# 33 - Épico
# 20 - Erótico
# 21 - Fantasia
# 22 - Faroeste
# 35 - Ficção
# 27 - Ficção Científica
# 23 - Guerra
# 11 - Horror
#  1 - Indefinido
# 31 - Infantil
# 24 - Musical
# 25 - Policial
# 12 - Romance
# 36 - Seriado
# 37 - Show
# 26 - Suspense
# 38 - Terror
# 40 - Thriller
# 39 - Western

def notify(body, summary='', icon=''):

    # Fallback for no notifications
    if not notifications:
        print "%s - %s" % (summary, body)
        return

    # Use the same interface object in all calls
    if not _globals['notifier']:
        _bus_name = 'org.freedesktop.Notifications'
        _bus_path = '/org/freedesktop/Notifications'
        _bus_obj  = dbus.SessionBus().get_object(_bus_name, _bus_path)
        _globals['notifier'] = dbus.Interface(_bus_obj, _bus_name)

    app_name    = _globals['apptitle']
    replaces_id = 0
    summary     = summary or app_name
    actions     = []
    hints       = {'x-canonical-append': "" }  # merge if same summary
    timeout     = -1 # server default

    if icon and os.path.exists(icon):
        _globals['notify_icon'] = icon # save for later
    app_icon    = _globals['notify_icon']

    _globals['notifier'].Notify(app_name, replaces_id, app_icon, summary, body,
                                actions, hints, timeout)
    print_debug("Notification: %s" % body)

def print_debug(text):
    if not debug: return
    print "%s\t%s" % (datetime.today(), '\n\t'.join(text.split('\n')))

def read_config():
    global login, password, debug, cache, similarity

    cp = ConfigParser.SafeConfigParser()
    config_file = os.path.join(_globals['config_dir'],
                               _globals['appname'] + ".ini")

    if not os.path.exists(config_file):
        if not os.path.isdir(_globals['config_dir']):
            os.makedirs(_globals['config_dir'])
        cp.add_section("Preferences")
        cp.set("Preferences", "login"     , str(login)) #FIXME: unicode!
        cp.set("Preferences", "password"  , str(password))
        cp.set("Preferences", "debug"     , str(debug))
        cp.set("Preferences", "cache"     , str(cache))
        cp.set("Preferences", "similarity", str(similarity))

        with open(config_file, 'w') as f:
            cp.write(f)

        if debug: sys.stderr.write("A blank config file was created at %s\n"
            "Please edit it and fill in login and password before using this"
            " module\n" % config_file)

        return

    cp.read(config_file)


    if cp.has_section("Preferences"):
        try:
            login      = cp.get("Preferences", "login")           or login
            password   = cp.get("Preferences", "password")        or password
            similarity = cp.getfloat("Preferences", "similarity") or similarity
            debug      = cp.getboolean("Preferences", "debug")
            cache      = cp.getboolean("Preferences", "cache")
        except:
            pass

    if not (login and password):
        sys.stderr.write("Login or password is blank. You won't be able to"
            " access Legendas.TV without it.\nPlease edit your config file"
            " at %s\nand fill them in\n" % config_file)

def fields_to_int(dict, *keys):
    """ Helper function to cast several fields in a dict to int
        usage: int_fields(mydict, 'keyA', 'keyB', 'keyD')
    """
    for key in keys:
        dict[key] = int(dict[key])

def get_similarity(text1, text2, ignorecase=True):
    """ Returns a float in [0,1] range representing the similarity of 2 strings
    """
    if ignorecase:
        text1 = text1.lower()
        text2 = text2.lower()
    return difflib.SequenceMatcher(None, text1, text2).ratio()

def choose_best_string(reference, candidates, ignorecase=True):
    """ Given a reference string and a list of candidate strings, return a dict
        with the candidate most similar to the reference, its index on the list
        and the similarity ratio (a float in [0, 1] range)
    """
    if ignorecase:
        reference_lower  = reference.lower()
        candidates_lower = [c.lower() for c in candidates]
        result = difflib.get_close_matches(reference_lower,
                                           candidates_lower,1, 0)[0]

        index = candidates_lower.index(result)
        best  = candidates[index]
        similarity = get_similarity(reference_lower, result, False)

    else:
        best = difflib.get_close_matches(reference, candidates, 1, 0)[0]
        index = candidates.index(best)
        similarity = get_similarity(reference, best, False)

    return dict(best = best,
                index = index,
                similarity = similarity)

def choose_best_by_key(reference, dictlist, key, ignorecase=True):
    """ Given a reference string and a list of dictionaries, compares each
        dict key value against the reference, and return a dict with keys:
        'best' = the dict whose key value was the most similar to reference
        'index' = the position of the chosen dict in dictlist
        'similarity' = the similarity ratio between reference and dict[key]
    """
    if ignorecase:
        best = choose_best_string(reference.lower(),
                                  [d[key].lower() for d in dictlist],
                                  ignorecase = False)
    else:
        best = choose_best_string(reference, [d[key] for d in dictlist], False)


    result = dict(best = dictlist[best['index']],
                  similarity = best['similarity'])
    print_debug("Chosen best for '%s' in '%s': %s" % (reference, key, result))
    return result

def clean_string(text):
    text = re.sub(r"^\[.+?]"   ,"",text)
    text = re.sub(r"[][}{)(.,:_-]"," ",text)
    text = re.sub(r" +"       ," ",text).strip()
    return text

def guess_movie_info(text):

    text = text.strip()

    # If 2+ years found, pick the last one and pray for a sane naming scheme
    year = re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", text)
    year = year[-1] if year else ""

    release = clean_string(text)

    if year:
        title = release.split(year,1)[1 if release.startswith(year) else 0]
    else:
        title = release

    # Remove some common "tags"
    tags = ['1080p','720p','480p','hdtv','h264','x264','h65','dts','aac','ac3',
            'bluray','bdrip','brrip','dvd','dvdrip','xvid','mp4','itunes',
            'web dl','blu ray']
    for s in tags:
        title = re.sub(s, "", title, re.IGNORECASE)
    title = re.sub(" +", " ", title).strip()

    result = dict(year=year, title=title, release=release)
    print_debug("Guessed title info: '%s' -> %s" % (text, result))
    return result

def filter_dict(dict, keys=[], whitelist=True):
    """ Filter a dict, returning a copy with only the selected keys
        (or all *but* the selected keys, if not whitelist)
    """
    if keys:
        if whitelist:
            return dict([(k, v) for (k, v) in dict.items() if k in keys])
        else:
            return dict([(k, v) for (k, v) in dict.items() if k not in keys])
    else:
        return dict

def print_dictlist(dictlist, keys=None, whitelist=True):
    """ Prints a list, an item per line """
    return "\n".join([repr(filter_dict(d, keys, whitelist))
                      for d in dictlist])

def extract_archive(archive, dir=None, extlist=[], keep=False):
    """ Extract files from a zip or rar archive whose filename extension
        (including the ".") is in extlist, or all files if extlist is empty.
        If keep is False, also delete the archive afterwards
        - archive is the archive filename (with path)
        - dir is the extraction folder, same folder as archive if empty
        return: a list with the filenames (with path) of extracted files
    """
    if not (dir and os.path.isdir(os.path.expanduser(dir))):
        dir = os.path.dirname(archive)

    files = []
    af = ArchiveFile(archive)
    for f in af.infolist():
        if not extlist or os.path.splitext(f.filename)[1].lower() in extlist:
            outfile = os.path.expanduser(os.path.join(dir, f.filename))
            with open(outfile, 'wb') as output:
                output.write(af.read(f))
                files.append(outfile)

    try:
        if not keep: os.remove(archive)
    except:
        pass # who cares?

    print_debug("Extracted archive '%s' (%s)\n%s" % (archive, extlist,
                                                    print_dictlist(files)))
    return files

def ArchiveFile(filename):
    """ Pseudo class (hence the Case) to wrap both rar and zip handling,
        since they both share almost identical API
        usage:  myarchive = ArchiveFile(filename)
        return: a RarFile or ZipFile instance (or None), depending on
                <filename> content
    """
    if   rarfile.is_rarfile(filename):
        return rarfile.RarFile(filename)
    elif zipfile.is_zipfile(filename):
        return zipfile.ZipFile(filename)
    else:
        return None

class HttpBot(object):
    """ Base class for other handling basic http tasks like requesting a page,
        download a file and cache content. Not to be used directly
    """
    def __init__(self, base_url=""):
        self._opener = urllib2.build_opener(urllib2.HTTPCookieProcessor())
        self.base_url = base_url

    def get(self, url, postdata=""):
        """ Send an HTTP request, either GET (if no postdata) or POST
            Keeps session and other cookies.
            postdata is a dict with name/value pairs
            url must be relative to base_url
        """
        if postdata:
            return self._opener.open(self.base_url + url,
                                     urllib.urlencode(postdata))
        else:
            return self._opener.open(self.base_url + url)

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
        filename = os.path.join(_globals['cache_dir'], os.path.basename(url))
        if os.path.exists(filename):
            return True
        else:
            return (self.download(url, _globals['cache_dir']))


class LegendasTV(HttpBot):

    def __init__(self, username, password):
        super(LegendasTV, self).__init__("http://legendas.tv/")
        url = "login_verificar.php"
        print_debug("Logging into %s as %s" % (self.base_url + url, username))
        self.get(url, {'txtLogin': username, 'txtSenha': password})

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
    _re_movie_data = re.compile(r"filme=(?P<id>\d+).+src=\\'(?P<thumb>[^']+)\\'")

    def getMovies(self, text, type=None):
        """ Given a search text, return a list of dicts with basic movie info:
            id, title, year, thumb (relative url for a thumbnail image)
        """
        movies = []

        tree = html.parse(self.get("index.php?opcao=buscarlegenda",
                                   self._searchdata(text, type)))

        #<table width="400" border="0" cellpadding="0" cellspacing="0" class="filmresult">
        #<tr>
        #    <td width="223"><div align="center"><strong>Filmes com legendas encontrados:</strong></div></td>
        #</tr>
        #<tr>
        #    <td>
        #        <div align="center">
        #            <a href="index.php?opcao=buscarlegenda&filme=28008" onMouseOver="this.T_OPACITY=95; this.T_OffsetY=30; this.T_WIDTH=150; return escape('<div align=\'center\'><img align=\'center\' src=\'thumbs/6ef0be5de6f424af7aa59a8040d0363d.jpg\'></div>');">WWE Randy Orton: The Evolution Of A Predator (2011)</a>
        #        </div>
        #    </td>
        #</tr>
        for e in tree.xpath(".//*[@class='filmresult']//a"):
            movie = {}
            movie.update(re.search(self._re_movie_text, e.text).groupdict())
            movie.update(re.search(self._re_movie_data,
                                   html.tostring(e)).groupdict())
            fields_to_int(movie, 'id', 'year')
            if cache: self.cache(movie['thumb'])
            movies.append(movie)

        print_debug("Titles found for '%s':\n%s" % (text,
                                                    print_dictlist(movies)))
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
        movie['year'] = int(clean_string(movie['year']))

        print_debug("Details for title %s: %s" % (id, movie))
        return movie

    """ Convenience wrappers for the main getSubtitles method """

    def getSubtitlesByMovie(self, movie, lang=None, allpages=True):
        return self.getSubtitles(movie_id=movie['id'],
                                 lang=lang, allpages=allpages)

    def getSubtitlesByMovieId(self, movie_id, lang=None, allpages=True):
        return self.getSubtitles(movie_id=movie_id,
                                 lang=lang, allpages=allpages)

    def getSubtitlesByText(self, text, type=None, lang=None, allpages=True):
        return self.getSubtitles(text=text, type=type,
                                 lang=lang, allpages=allpages)

    _re_sub_language = re.compile(r"flag_(\w+)\.")
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
        abredown\('(?P<id>\w+)'\).*
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
        subtitles = []

        url = "index.php?opcao=buscarlegenda"
        if movie_id:
            url +=  "&filme=" + str(movie_id)
            text = ".." # Irrelevant to search, but must have at least 2 chars

        # Post data is saved on server, along with session data,
        # so it must be posted at least once, even when searching by movie_id
        postdata = self._searchdata(text, type, lang)

        page = 0
        lastpage = False
        while not lastpage:
            page += 1
            tree = html.parse(self.get(url, postdata))

            #<span onmouseover="this.T_OPACITY=95; this.T_WIDTH=400; return escape(gpop('Predators','Predadores','Predators.2010.R5.LiNE.XviD-Noir','1','23','1370MB','30655','<img src=\'images/flag_br.gif\' border=\'0\'>','26/09/2010 - 12:02'))">
            #<table width="100%" onclick="javascript:abredown('9563521bbb4041f77223e04c1dc47d02');" class="buscaDestaque" bgcolor="#F7D36A">
            #  <tr>
            #    <td rowspan="2" scope="col" style="width:5%"><img src="images/gold.gif" border="0"></td>
            #    <td scope="col" style="width:45%" class="mais"><b>Predators</b><br />Predadores<br/><b>Downloads: </b> 30655 <b>Comentários: </b>160<br><b>Avaliação: </b> 10/10</td>
            #    <td scope="col" style="width:20%">26/09/2010 - 12:02</td>
            #    <td scope="col" style="width:20%"><a href="javascript:abreinfousuario(577204)">inSanos</a></td>
            #    <td scope="col" style="width:10%"><img src='images/flag_br.gif' border='0'></td>
            #  </tr>
            #  <tr>
            #    <td colspan="4">Release: <span class="brls">Predators.2010.R5.LiNE.XviD-Noir</span></td>
            #  </tr>
            #</table>
            #</span>
            for e in tree.xpath(".//*[@id='conteudodest']/*/span"):
                data = e.xpath(".//text()")
                htmltext = html.tostring(e)
                sub = {}
                sub.update(dict(
                    title       = data[ 1],
                    title_br    = data[ 2],
                    downloads   = data[ 4],
                    comments    = data[ 6],
                    rating      = data[ 8].split("/")[0].strip(),
                    date        = data[10],
                    user_name   = data[12],
                    release     = data[16],
                ))
                sub.update(re.search(self._re_sub_text, htmltext).groupdict())
                fields_to_int(sub, 'downloads', 'comments', 'cds',
                                   'fps', 'size', 'user_id')
                sub['language'] = re.search(self._re_sub_language,
                                            sub['flag']).group(1)
                sub['gold'] = ("images/gold.gif" in htmltext)
                sub['highlight'] = ("buscaDestaque" in htmltext)
                sub['date'] = datetime.strptime(sub['date'], '%d/%m/%Y - %H:%M')
                if sub['release'].startswith("(p)"):
                    sub['release'] = sub['release'][3:]
                    sub['pack'] = True
                else:
                    sub['pack'] = False

                if cache: self.cache(sub['flag'])
                subtitles.append(sub)

            # Page control
            if not allpages:
                lastpage = True
            else:
                prevnext = tree.xpath("//a[@class='btavvt']")
                if len(prevnext) > 1:
                    # bug at page 9: url for next page points to current page,
                    # so we need to manually fix it
                    url = prevnext[1].attrib['href'].replace("pagina=" + str(page),
                                                             "pagina=" + str(page+1))
                    postdata = "" # must not post data for pages > 1
                else:
                    lastpage = True

        print_debug("Subtitles found for %s:\n%s" %
                   ( movie_id or "'%s'" % text, print_dictlist(subtitles)))
        return subtitles

    def getSubtitleDetails(self, id):
        """ Returns a dict with additional info about a subtitle than the ones
            provided by getSubtitles(), such as:
            imdb_url, description (html), updates (list), votes
            As with getSubtitles(), some info are related to the movie, not to
            that particular subtitle
        """
        sub = {}
        tree = html.parse(self.get('info.php?d=' + id))

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
            votes       = info_from_list(data, "Votos:"),
            user_name   = info_from_list(data, "Enviada por:"),
            date        = info_from_list(data, "Em:"),
        ))
        sub['date'] = datetime.strptime(sub['date'], '%d/%m/%Y - %H:%M')

        fields_to_int(sub, 'year', 'downloads', 'comments', 'cds', 'fps',
                           'size', 'votes')

        print_debug("Details for subtitle '%s': %s" % (id, sub))
        return sub

    def downloadSubtitle(self, id, dir, basename=""):
        """ Download a subtitle archive based on subtitle id.
            Saves the archive as dir/basename, using the basename provided or,
            if empty, the one returned from the website.
            Return the filename (with full path) of the downloaded archive
        """
        print_debug("Downloading archive for subtitle '%s'" % id)
        result = self.download('info.php?c=1&d=' + id, dir, basename)
        print_debug("Archive saved as '%s'" % (result))
        return result

    def rankSubtitles(self, movie, subtitles):
        """ Evaluates each subtitle based on wanted movie and give each a score.
            Return the list sorted by score, greatest first
        """
        # Idea for a improvements on ranking system (points):
        # 2 - Number of CDs (1 for 0, 2 for exact, 0 for wrong)
        # 2 - Size +-15% (1 for 0/1MB, 0 for wrong)
        # ** = time-sentitive: must be wheigted by oldest

        def days(d):
            return (datetime.today() - d).days

        max_comments = max([s['comments'] for s in subtitles])
        oldest = days(min([s['date'] for s in subtitles]))
        newest = days(max([s['date'] for s in subtitles]))

        for sub in subtitles:
            score = 0

            score +=10 * max(get_similarity(movie['title'],sub['title']),
                             get_similarity(movie['title'],sub['title_br']))
            score += 3 * 1 if sub['gold'] else 0
            score += 1 * 1 if sub['highlight'] else 0
            score += 2 * get_similarity(movie['release'],
                                        clean_string(sub['release']))
            score += 1 * (int(sub['rating'])/10 if sub['rating'].isdigit()
                                                else 1)
            score += 2 * (sub['comments']/max_comments)
            score += 1 * (1 - ( (days(sub['date'])-newest)/(oldest-newest)
                                if oldest != newest
                                else 0 ))

            sub['score'] = 10 * score / 20

        result = sorted(subtitles, key=operator.itemgetter('score'),reverse=True)
        print_debug("Ranked subtitles for %s:\n%s" % (movie,
                                                      print_dictlist(result)))
        return result


read_config()

if __name__ == "__main__" and login and password:

    # scrap area, with a common workflow...

    # Log in
    notify("Logging in Legendas.TV")
    legendastv = LegendasTV(login, password)

    examples = [
        "~/Videos/Encouraçado Potemkin+/"
            "The Battleship Potemkin (Sergei M. Eisenstein, 1925).avi",
        "~/Videos/Dancer.In.The.Dark.[2000].DVDRip.XviD-BLiTZKRiEG.avi",
        "~/Videos/The.Raven.2012.720p.BluRay.x264-iNFAMOUS[EtHD]/"
            "inf-raven720p.mkv",
        "~/Videos/[ UsaBit.com ] - J.Edgar.2011.720p.BluRay.x264-SPARKS/"
            "sparks-jedgar-720.mkv",
        "~/Videos/Thor.2011.720p.BluRay.x264-Felony/f-thor.720.mkv",
        "~/Videos/Universal Soldier-720p MP4 AAC x264 BRRip 1992-CC/"
            "Universal Soldier-720p MP4 AAC x264 BRRip 1992-CC.mp4",
        "~/Videos/2012 2009 BluRay 720p DTS x264-3Li/2012 2009 3Li BluRay.mkv",
    ]

    # User selects a movie...
    try:
        usermovie = unicode(sys.argv[1], "utf-8")
    except:
        usermovie = os.path.expanduser(examples[0])
    print_debug("Target: %s" % usermovie)

    savedir = os.path.dirname(usermovie)
    dirname = os.path.basename(savedir)
    filename = os.path.splitext(os.path.basename(usermovie))[0]

    # Which string we use first for searches? Dirname or Filename?
    # If they are similar, take the dir. If not, take the longest
    if get_similarity(dirname, filename) > similarity or \
       len(dirname) > len(filename):
        search = dirname
    else:
        search = filename

    # Now let's play with that string and try to get some useful info
    movie = guess_movie_info(search)
    notify("Searching for '%s'" % movie['title'])

    # Let's begin with a movie search
    if len(movie['title']) >= 2:
        movies = legendastv.getMovies(movie['title'], 2)
    else:
        # quite a corner case, but still... title + year on release
        movies = legendastv.getMovies("%s %s" % (movie['title'],
                                                 movie['year']), 1) + \
                 legendastv.getMovies("%s %s" % (movie['title'],
                                                 movie['year']), 2)

    if len(movies) > 0:
        # Nice! Lets pick the best movie...
        notify("%s titles found" % len(movies))
        for m in movies:
            # Fist, clean up title...
            title = clean_string(m['title'])
            if title.endswith(" %s" % m['year']):
                title = title[:-5]

            # Now add a helper field
            m['search'] = "%s %s" % (title, m['year'])

        # May the Force be with... the most similar!
        result = choose_best_by_key("%s %s" % (movie['title'],
                                               movie['year']),
                                    movies,
                                    'search')

        # But... Is it really similar? Maybe results were capped at 10
        if result['similarity'] > similarity or len(movies)<10:
            movie.update(result['best'])
            notify("Searching title '%s' (%s)" % (result['best']['title'],
                                                  result['best']['year']),
                   icon=os.path.join(_globals['cache_dir'],
                                     os.path.basename(result['best']['thumb'])))
            subs = legendastv.getSubtitlesByMovie(movie)

        else:
            # Almost giving up... forget movie matching
            notify("None was similar enough. Trying release...")
            subs = legendastv.getSubtitlesByText("%s %s" %
                                                 (movie['title'],
                                                  movie['year']), 1)

    else:
        # Ok, let's try by release...
        notify("No titles found. Trying release...")
        subs = legendastv.getSubtitlesByText(movie['title'], 1)

    if len(subs) > 0:

        # Good! Lets choose and download the best subtitle...
        notify("%s subtitles found" % len(subs))

        subtitles = legendastv.rankSubtitles(movie, subs)

        # UI suggestion: present the user with a single subtitle, and the
        # following message:
        # "This is the best subtitle match we've found, how about it?"
        # And 3 options:
        # - "Yes, perfect, you nailed it! Download it for me"
        # - "This is nice, but not there yet. Let's see what else you've found"
        #   (show a list of the other subtitles found)
        # - "Eww, not even close! Let's try other search options"
        #   (show the search options used, let user edit them, and retry)

        notify("Downloading '%s' from '%s'" % (subtitles[0]['release'],
                                               subtitles[0]['user_name']))
        archive = legendastv.downloadSubtitle(subtitles[0]['id'], savedir)
        files = extract_archive(archive, savedir, [".srt"])
        if len(files) > 1:
            # Damn those multi-file archives!
            notify("%s subtitles in archive" % len(files))

            # Build a new list suitable for comparing
            files = [dict(compare=clean_string(os.path.basename(
                                               os.path.splitext(f)[0])),
                          original=f)
                     for f in files]

            # Should we use file or dir as a reference?
            dirname_compare  = clean_string(dirname)
            filename_compare = clean_string(filename)
            if get_similarity(dirname_compare , files[0]['compare']) > \
               get_similarity(filename_compare, files[0]['compare']):
                result = choose_best_by_key(dirname_compare,
                                            files, 'compare')
            else:
                result = choose_best_by_key(filename_compare,
                                            files, 'compare')

            file = result['best']
            files.remove(file) # remove the chosen from list
            [os.remove(f['original']) for f in files] # delete the list
            file = result['best']['original'] # convert back to string
        else:
            file = files[0] # so much easier...

        newname = os.path.join(savedir, filename) + ".srt"
        notify("Matching '%s'" % os.path.basename(file))
        os.rename(file, newname)
        notify("DONE!")

    else:
        # Are you *sure* this movie exists? Try our interactive mode
        # and search for yourself. I swear I tried...
        notify("No subtitles found")
