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
# - use a config file for settings, including login username and passowrd
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
import urllib
import urllib2
from lxml import html
from datetime import datetime
import difflib
import rarfile
import zipfile

username = ""
password = ""


# Languages [and flag names (country "codes")]:
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

debug = True
cache = False
min_similarity = 0.7

appname = "legendas"
dir_cache = os.path.join(os.environ.get('XDG_CACHE_HOME') or
                         os.path.join(os.path.expanduser('~'), '.cache'),
                         appname)
dir_prefs = os.path.join(os.environ.get('XDG_CONFIG_HOME') or
                         os.path.join(os.path.expanduser('~'), '.config'),
                         appname)

def fields_to_int(dict, *keys):
    """ Helper function to cast several fields in a dict to int
        usage: int_fields(mydict, 'keyA', 'keyB', 'keyD')
    """
    for key in keys:
        dict[key] = int(dict[key])

def get_similarity(text1, text2, ignorecase=True):
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
    """ Given a reference string and a list of candidate strings, return a dict
        with the candidate most similar to the reference, its index on the list
        and the similarity ratio (a float in [0, 1] range)
    """
    if ignorecase:
        best = choose_best_string(reference.lower(),
                                  [d[key].lower() for d in dictlist],
                                  ignorecase = False)
    else:
        best = choose_best_string(reference, [d[key] for d in dictlist], False)


    return dict(best = dictlist[best['index']],
                similarity = best['similarity'])

def clean_string(text):
    text = re.sub(r"^\[.+?]"   ,"",text)
    text = re.sub(r"[][}{)(._-]"," ",text)
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
        title = re.sub(s, "", title, flags=re.IGNORECASE)
    title = re.sub(" +", " ", title).strip()

    return dict(original=text, year=year, title=title, release=release)

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

    extractedfiles = []
    af = ArchiveFile(archive)
    for f in af.infolist():
        if not extlist or os.path.splitext(f.filename)[1].lower() in extlist:
            if debug: print "Extracting " + f.filename

            outfile = os.path.expanduser(os.path.join(dir, f.filename))
            with open(outfile, 'wb') as output:
                output.write(af.read(f))
                extractedfiles.append(outfile)

    try:
        if not keep: os.remove(archive)
    except:
        pass # who cares?

    return extractedfiles

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

class Movie(object):
    def __init__(self, id, **kw):
        self.id = id
        for k, v in kw.iteritems(): setattr(self, k, v)

class HttpBot(object):
    """ Base class for other handling basic http tasks like requesting a page,
        download a file and cache content
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
        filename = os.path.join(dir_cache, os.path.basename(url))
        if os.path.exists(filename):
            return True
        else:
            return (self.download(url, dir_cache))


class LegendasTV(HttpBot):

    def __init__(self, username, password):
        super(LegendasTV, self).__init__("http://legendas.tv/")
        self.get("login_verificar.php",
                 {'txtLogin': username,
                  'txtSenha': password})

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
            ID, Title, Year, Thumb
        """
        movies = []

        tree = html.parse(self.get("index.php?opcao=buscarlegenda",
                                   self._searchdata(text, type)))
        #tree = html.parse(open("filmes.html"))

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

        if debug: print str(len(movies)) + " movies found"
        return movies

    def getMovieDetailsById(self, id):
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
        e = tree.xpath(".//table[@class='filmresult']")[0]
        data = e.xpath(".//text()")

        #TODO: Looking good, now parse it! :)
        return data




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

    _re_sub_country = re.compile(r"flag_(\w+)\.")
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
        """Either text or movie_id must be provided"""
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
                text = html.tostring(e)
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
                sub.update(re.search(self._re_sub_text, text).groupdict())
                fields_to_int(sub, 'downloads', 'comments', 'cds',
                                   'fps', 'size', 'user_id')
                sub['country'] = re.search(self._re_sub_country,
                                           sub['flag']).group(1)
                sub['gold'] = ("images/gold.gif" in text)
                sub['highlight'] = ("buscaDestaque" in text)
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

        if debug: print str(len(subtitles)) + " subtitles found"
        return subtitles

    def getSubtitleDetails(self, id):
        #TODO: Parse it! :)
        return self.get('info.php?d=' + id).read()
        #tree = html.parse(self.get('info.php?d=' + id))

    def downloadSubtitle(self, id, dir, filename=""):
        return self.download('info.php?c=1&d=' + id, dir, filename)

    def rankSubtitles(self, movie, subtitles):
        # TODO: Come on, don't be lazy.. rank them!
        return subtitles

if __name__ == "__main__":

    # scrap area, with a common workflow...

    # Log in
    legendastv = LegendasTV(username, password)

    examples = [
        "~/Videos/2012 2009 BluRay 720p DTS x264-3Li/2012 2009 3Li BluRay.mkv",
        "~/Videos/Dancer.In.The.Dark.[2000].DVDRip.XviD-BLiTZKRiEG.avi",
        "~/Videos/The.Raven.2012.720p.BluRay.x264-iNFAMOUS[EtHD]/"
            "inf-raven720p.mkv",
        "~/Videos/[ UsaBit.com ] - J.Edgar.2011.720p.BluRay.x264-SPARKS/"
            "sparks-jedgar-720.mkv",
        "~/Videos/Thor.2011.720p.BluRay.x264-Felony/f-thor.720.mkv",
        "~/Videos/Universal Soldier-720p MP4 AAC x264 BRRip 1992-CC/"
            "Universal Soldier-720p MP4 AAC x264 BRRip 1992-CC.mp4",
    ]

    # User selects a movie...
    for usermovie in [os.path.expanduser(e) for e in examples]:

        savedir = os.path.dirname(usermovie)
        dirname = os.path.basename(savedir)
        filename = os.path.splitext(os.path.basename(usermovie))[0]

        # Which string we use first for searches? Dirname or Filename?
        # If they are similar, take the dir. If not, take the longest
        if get_similarity(dirname, filename)>0.4 or len(dirname)>len(filename):
            searchlist = (dirname, filename)
        else:
            searchlist = (filename, dirname)

        for search in searchlist:

            # Now let's play with that string and try to get some useful info
            movie = guess_movie_info(search)
            print "Search parameters: %s" % movie

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
                print "Chosen movie: %s" % result

                # But... Is it really similar? Maybe results were capped at 10
                if result['similarity'] > min_similarity or len(movies)<10:
                    movie.update(result['best'])
                    subs = legendastv.getSubtitlesByMovie(movie)

                else:
                    # Almost giving up... forget movie matching
                    print "Not similar enough. Retrying..."
                    subs = legendastv.getSubtitlesByText("%s %s" %
                                                         (movie['title'],
                                                          movie['year']), 1)

            else:
                # Ok, let's try by release...
                subs = legendastv.getSubtitlesByText(movie['title'], 1)

            if len(subs) > 0:

                # Good! Lets choose and download the best subtitle...
                subtitles = legendastv.rankSubtitles(movie, subs)
                print "Chosen subtitle: %s" % subtitles[0]

                # UI suggestion: present the user with a single subtitle, and the
                # following message:
                # "This is the best subtitle match we've found, how about it?"
                # And 3 options:
                # - "Yes, perfect, you nailed it! Download it for me"
                # - "This is nice, but not there yet. Let's see what else you've found"
                #   (show a list of the other subtitles found)
                # - "Eww, not even close! Let's try other search options"
                #   (show the search options used, let user edit them, and retry)

                #TODO: Cache the archives so we don't download them over and over.....,
                archive = legendastv.downloadSubtitle(subtitles[0]['id'], savedir)
                files = extract_archive(archive, savedir, [".srt"])
                if len(files) > 1:
                    # Damn those multi-file archives!
                    # TODO: Clean up extracted filenames for a fair compare.
                    # also, create a function that compares both filename and
                    # release, let the file score be the higher of them
                    file = choose_best_string(usermovie, files)['best']
                    files.remove(file)
                    [os.remove(f) for f in files]
                else:
                    file = files[0]
                newname = os.path.join(os.path.expanduser('~'), filename) + ".srt"
                print "Renaming %s to %s" % (file, newname)
                os.rename(file, newname)

            else:
                # Are you *sure* this movie exists? Try our interactive mode
                # and search for yourself. I swear I tried...
                print "No subtitles found. I give up..."

            break
