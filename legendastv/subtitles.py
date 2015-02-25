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
import shutil
import logging

from . import g, datatools as dt, filetools as ft, srtclean
from .providers import opensubtitles, legendastv as ltv
from .utils import notify, print_debug

log = logging.getLogger(__name__)

_provider = None
_re_season_episode = re.compile(r"[S]?(?P<season>\d\d?)[Ex](?P<episode>\d\d?)",
                                re.IGNORECASE)

def guess_movie_info(text):

    text = text.strip()

    # If 2+ years found, pick the last one and pray for a sane naming scheme
    year = re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", text)
    year = year[-1] if year else ""

    release = dt.clean_string(text)

    if year:
        title = release.split(year,1)[1 if release.startswith(year) else 0]
    else:
        title = release

    # Remove some common "tags"
    tags = ['1080p','720p','480p','hdtv','h264','x264','h65','dts','aac','ac3',
            'bluray','bdrip','brrip','dvd','dvdrip','xvid','mp4','itunes',
            'web dl','blu ray']
    for s in tags:
        title = re.sub(s, "", title, 0, re.IGNORECASE)
    title = re.sub(" +", " ", title).strip()

    result = dict(year=year, title=title, release=release)
    print_debug("Guessed title info: '%s' -> %s" % (text, result))
    return result


def get_provider():
    """A convenience function to allow re-usage of a provider instance
        with a single initialization
    """
    global _provider

    if _provider is not None:
        return _provider

    notify("Logging in Legendas.TV", icon=g.globals['appicon'])
    _provider = ltv.LegendasTV()
    _provider.login(g.options['login'],
                    g.options['password'])

    if not _provider.auth:
        raise g.LegendasError("Login failed, check your config file!")

    return _provider


def retrieve_subtitle_for_movie(usermovie, login=None, password=None,
                                remote=False):
    """ Main function to find, download, extract and match a subtitle for a
        selected file
    """
    usermovie = os.path.abspath(usermovie)
    print_debug("Target: %s" % usermovie)
    savedir = os.path.dirname(usermovie)
    dirname = os.path.basename(savedir)
    filename = os.path.splitext(os.path.basename(usermovie))[0]

    # Which string we use first for searches? Dirname or Filename?
    # Use Filename unless Dirname is much longer (presumably more relevant info)
    if len(dirname) > 2 * len(filename):
        search = dirname
    else:
        search = filename

    # Now let's play with that string and try to get some useful info
    movie = guess_movie_info(search)
    movie.update({'episode': '',
                  'season': '',
                  'type': '',
                  'dirname': dirname,
                  'filename': filename})

    # Try to tell movie from episode
    data_obj = re.search(_re_season_episode, filename) # always use filename
    if data_obj:
        data = data_obj.groupdict()
        movie['type']    = 'episode'
        movie['season']  = data['season']
        movie['episode'] = data['episode']
        movie['title']   = movie['title'][:data_obj.start()].strip()

    # Get more useful info from OpenSubtitles.org
    # Only for local files, as the hashing used for video ID
    #  requires a full file copy over remote mounts (FTP/SSH)
    if not remote:
        movie = update_movie_with_osdb(usermovie, movie)

    def season_to_ord(season):
        season = int(season)
        if   season == 1: tag = "st"
        elif season == 2: tag = "nd"
        elif season == 3: tag = "rd"
        else            : tag = "th"
        return "%d%s" % (season, tag)

    legendastv = get_provider()

    # Let's begin with a movie search
    if movie['type'] == 'episode':
        movie['release'] = dt.clean_string(filename)
        notify("Searching titles for '%s %s Season'",
               movie['title'],
               season_to_ord(movie['season']),
               icon=g.globals['appicon'])
    else:
        notify("Searching titles for '%s'", movie['title'],
               icon=g.globals['appicon'])

    movies = legendastv.getMovies(movie['title'])

    if len(movies) > 0:
        # Nice! Lets pick the best movie...
        notify("%s titles found", len(movies))

        # For Series, add Season to title and compare with native title
        if movie['type'] == 'episode':
            season = " %d" % int(movie['season'])
            search = 'title_br'
        else:
            season = ""
            search = 'title'

        for m in movies:
            # Add a helper field: cleaned-up title
            m['search'] = dt.clean_string(m[search])
            # For episodes, clean further
            if movie['type'] == 'episode':
                for tag in ['Temporada', 'temporada', 'Season', 'season', u'\xaa']:
                    m['search'] = m['search'].replace(tag, "")
                m['search'] = m['search'].strip()

        # May the Force be with... the most similar!
        title_to_search = dt.clean_string(g.mapping.get(movie['title'].lower(), movie['title']))
        result = dt.choose_best_by_key(title_to_search + season, movies, 'search')

        # But... Is it really similar?
        if len(movies) == 1 or result['similarity'] > g.options['similarity']:
            movie.update(result['best'])

            if movie['type'] == 'episode':
                notify("Searching subs for '%s' - Episode %d",
                       result['best']['title_br'],
                       int(movie['episode']),
                       icon=os.path.join(g.globals['cache_dir'], 'thumbs',
                                         os.path.basename(result['best']['thumb'] or "")))
            else:
                notify("Searching subs for '%s'", result['best']['title'],
                       icon=os.path.join(g.globals['cache_dir'], 'thumbs',
                                         os.path.basename(result['best']['thumb'] or "")))

            subs = legendastv.getSubtitlesByMovie(movie)

        else:
            # Almost giving up... forget movie matching
            notify("None was similar enough. Trying release...")
            subs = legendastv.getSubtitlesByText(movie['release'])

    else:
        # Ok, let's try by release...
        notify("No titles found. Trying release...")
        subs = legendastv.getSubtitlesByText(movie['release'])

    if not subs:
        # Are you *sure* this movie exists? Try our interactive mode
        # and search for yourself. I swear I tried...
        notify("No subtitles found")
        return False

    # Good! Lets choose and download the best subtitle...
    notify("%s subtitles found", len(subs))

    try:
        subtitle = choose_subtitle(movie, subs)
    except g.LegendasError as e:
        notify(e)
        return

    notify("Downloading '%s' from '%s'",
           subtitle['release'],
           subtitle['user_name'])

    archive = legendastv.downloadSubtitle(subtitle['hash'],
                                          os.path.join(g.globals['cache_dir'],
                                                       'archives'),
                                          overwrite=False)
    if not archive:
        notify("ERROR downloading archive!")
        return

    try:
        srtfile = choose_srt(movie, archive)
    except g.LegendasError as e:
        notify(e)
        return

    srtclean.main(['--in-place', '--convert', 'UTF-8', srtfile])
    srtbackup = "%s.srtclean.bak" % srtfile
    # If srtclean modified the subtitle,
    # rename the modified file and revert the backup
    if os.path.isfile(srtbackup):
        cleanfile = "%s.srtclean.srt" % os.path.splitext(srtfile)[0]
        os.rename(srtfile, cleanfile)
        os.rename(srtbackup, srtfile)
        srtfile = cleanfile
    shutil.copyfile(srtfile, os.path.join(savedir, "%s.srt" % filename))
    notify("DONE!")
    return True


def update_movie_with_osdb(path, movie):
    osdb_movie = find_osdb_movie(path, movie)

    if not osdb_movie:
        return movie

    # For episodes, extract only the series name
    if (osdb_movie['MovieKind'] == 'episode' and
        osdb_movie['MovieName'].startswith('"')):
        osdb_movie['MovieName'] = osdb_movie['MovieName'].split('"')[1]

    movie['title']   = osdb_movie['MovieName']
    movie['year']    = osdb_movie['MovieYear']
    movie['type']    = movie['type']    or osdb_movie['MovieKind']
    movie['season']  = movie['season']  or osdb_movie['SeriesSeason']
    movie['episode'] = movie['episode'] or osdb_movie['SeriesEpisode']

    return movie


def find_osdb_movie(path, movie):
    # Search OSDB by hash and get filtered list of results
    osdb_movies = [m for m in opensubtitles.videoinfo(path)
                   if m['MovieKind'] != 'tv series' and
                   (not movie['type'] or m['MovieKind']==movie['type'])]

    print_debug("%d OpenSubtitles titles found:\n%s" %
                (len(osdb_movies), dt.print_dictlist(osdb_movies)))

    if not osdb_movies:
        return

    # Thats the one!
    if len(osdb_movies) == 1:
        return osdb_movies[0]

    # Craft the reference search, using title and year, if available
    search = movie['title']
    if movie['year']:
        search += " %s" % movie['year']

    # Prepare candidates
    for m in osdb_movies:
        m['search'] = m['MovieName']
        if movie['year']:
            m['search'] += " %s" % m['MovieYear']

    return dt.choose_best_by_key(search, osdb_movies, 'search')['best']


def choose_subtitle(movie, subs):
    """Choose a subtitle from subs for a movie"""

    legendastv = get_provider()

    # For TV Series, consider only packs and matching episodes
    if movie['type'] == 'episode':
        episodes = []
        for sub in subs:
            data_obj = re.search(_re_season_episode, sub['release'])
            # Check whether the episode matches. The subtitle should never
            # be selected if the episode doesn't match, even if it's a pack.
            if data_obj:
                data = data_obj.groupdict()
                if int(data['episode']) == int(movie['episode']):
                    episodes.append(sub)
            elif sub['pack']:
                episodes.append(sub)
        subs = episodes

    subtitles = legendastv.rankSubtitles(movie, subs)
    if not subtitles:
        raise g.LegendasError("No subtitles found for episode %d" %
                              int(movie['episode']))

    return subtitles[0]


def choose_srt(movie, archive):
    """Extract an archive and choose an srt file for a movie"""

    files = ft.extract_archive(archive, extlist=["srt"])
    if not files:
        raise g.LegendasError("ERROR! Archive is corrupt or has no subtitles")

    if len(files) == 1:
        return files[0]  # so much easier...

    # Damn those multi-file archives!
    notify("%s subtitles in archive", len(files))

    # Build a new list suitable for comparing
    files = [dict(compare=dt.clean_string(os.path.basename(os.path.splitext(f)[0])),
                  original=os.path.basename(f),
                  full=f)
             for f in files]

    # If Series, match by Episode
    srt = None
    if movie['type'] == 'episode':
        for item in files:
            data_obj = re.search(_re_season_episode, item['original'])
            if data_obj:
                data = data_obj.groupdict()
                if int(data['episode']) == int(movie['episode']):
                    item['similarity'] = dt.get_similarity(movie['release'],
                                                           item['compare'])
                    if not srt or item['similarity'] > srt['similarity']:
                        srt = item
        if srt:
            print_debug("Chosen for episode %s: %s" % (movie['episode'],
                                                       srt['original']))
    if not srt:
        # Use name/release matching
        # Should we use file or dir as a reference?
        dirname_compare  = dt.clean_string(movie['dirname'])
        filename_compare = dt.clean_string(movie['filename'])
        if movie['type'] == 'episode' or \
           dt.get_similarity(dirname_compare , files[0]['compare']) < \
           dt.get_similarity(filename_compare, files[0]['compare']):
            result = dt.choose_best_by_key(filename_compare,
                                           files, 'compare')
        else:
            result = dt.choose_best_by_key(dirname_compare,
                                           files, 'compare')
        srt = result['best']

    return srt['full'] # convert back to string
