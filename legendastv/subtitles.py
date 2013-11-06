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
import dbus
import logging

from . import g, datatools as dt, filetools as ft
from .providers import opensubtitles

log = logging.getLogger(__name__)


def notify(body, summary='', icon=''):

    # Fallback for no notifications
    if not g.options['notifications']:
        log.notify("%s - %s", summary, body)
        return

    # Use the same interface object in all calls
    if not g.globals['notifier']:
        _bus_name = 'org.freedesktop.Notifications'
        _bus_path = '/org/freedesktop/Notifications'
        _bus_obj  = dbus.SessionBus().get_object(_bus_name, _bus_path)
        g.globals['notifier'] = dbus.Interface(_bus_obj, _bus_name)

    app_name    = g.globals['apptitle']
    replaces_id = 0
    summary     = summary or app_name
    actions     = []
    hints       = {'x-canonical-append': "" }  # merge if same summary
    timeout     = -1 # server default

    if icon and os.path.exists(icon):
        g.globals['notify_icon'] = icon # save for later
    app_icon    = g.globals['notify_icon']

    g.globals['notifier'].Notify(app_name, replaces_id, app_icon, summary, body,
                                actions, hints, timeout)
    log.notify(body)


def print_debug(text):
    log.debug('\n\t'.join(text.split('\n')))


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


def retrieve_subtitle_for_movie(usermovie, login=None, password=None,
                                legendastv=None):
    """ Main function to find, download, extract and match a subtitle for a
        selected file
    """

    # Log in
    if not legendastv:
        notify("Logging in Legendas.TV", icon=g.globals['appicon'])
        legendastv = legendastv.LegendasTV(login, password)

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
    movie.update({'episode': '', 'season': '', 'type': '' })

    # Try to tell movie from episode
    _re_season_episode = re.compile(r"S(?P<season>\d\d?)E(?P<episode>\d\d?)",
                                    re.IGNORECASE)
    data_obj = re.search(_re_season_episode, filename) # always use filename
    if data_obj:
        data = data_obj.groupdict()
        movie['type']    = 'episode'
        movie['season']  = data['season']
        movie['episode'] = data['episode']
        movie['title']   = movie['title'][:data_obj.start()]

    # Get more useful info from OpenSubtitles.org
    osdb_movies = []
    try:
        osdb_movies = opensubtitles.videoinfo(usermovie)
    except:
        pass

    # Filter results
    osdb_movies = [m for m in osdb_movies
                   if m['MovieKind'] != 'tv series' and
                   (not movie['type'] or m['MovieKind']==movie['type'])]

    print_debug("%d OpenSubtitles titles found:\n%s" %
                (len(osdb_movies), dt.print_dictlist(osdb_movies)))

    if len(osdb_movies) > 0:
        if movie['year']:
            search = "%s %s" % (movie['title'], movie['year'])
        else:
            search = movie['title']

        for m in osdb_movies:
            m['search'] = m['MovieName']
            if movie['year']:
                m['search'] += " %s" % m['MovieYear']

        osdb_movie = dt.choose_best_by_key(search, osdb_movies, 'search')['best']

        # For episodes, extract only the series name
        if (osdb_movie['MovieKind'] == 'episode' and
            osdb_movie['MovieName'].startswith('"')):
            osdb_movie['MovieName'] = osdb_movie['MovieName'].split('"')[1]

        movie['title']   = osdb_movie['MovieName']
        movie['year']    = osdb_movie['MovieYear']
        movie['type']    = movie['type']    or osdb_movie['MovieKind']
        movie['season']  = movie['season']  or osdb_movie['SeriesSeason']
        movie['episode'] = movie['episode'] or osdb_movie['SeriesEpisode']

    def season_to_ord(season):
        season = int(season)
        if   season == 1: tag = "st"
        elif season == 2: tag = "nd"
        elif season == 3: tag = "rd"
        else            : tag = "th"
        return "%d%s" % (season, tag)

    # Let's begin with a movie search
    if movie['type'] == 'episode':
        movie['release'] = dt.clean_string(filename)
        notify("Searching titles for '%s %s Season'" % (movie['title'],
                                                        season_to_ord(movie['season'])),
               icon=g.globals['appicon'])
    else:
        notify("Searching titles for '%s'" % movie['title'],
               icon=g.globals['appicon'])

    movies = legendastv.getMovies(movie['title'])

    if len(movies) > 0:
        # Nice! Lets pick the best movie...
        notify("%s titles found" % len(movies))

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

        # May the Force be with... the most similar!
        result = dt.choose_best_by_key(dt.clean_string(movie['title']) + season,
                                       movies, 'search')

        # But... Is it really similar?
        if result['similarity'] > g.options['similarity']:
            movie.update(result['best'])

            if movie['type'] == 'episode':
                notify("Searching subs for '%s' - Episode %d" %
                       (result['best']['title_br'], int(movie['episode'])),
                       icon=os.path.join(g.globals['cache_dir'],
                                         os.path.basename(result['best']['thumb'])))
            else:
                notify("Searching subs for '%s'" % (result['best']['title']),
                       icon=os.path.join(g.globals['cache_dir'],
                                         os.path.basename(result['best']['thumb'])))

            subs = legendastv.getSubtitlesByMovie(movie)

        else:
            # Almost giving up... forget movie matching
            notify("None was similar enough. Trying release...")
            subs = legendastv.getSubtitlesByText(movie['release'])

    else:
        # Ok, let's try by release...
        notify("No titles found. Trying release...")
        subs = legendastv.getSubtitlesByText(movie['release'])

    if len(subs) > 0:

        # Good! Lets choose and download the best subtitle...
        notify("%s subtitles found" % len(subs))

        # For TV Series, exclude the ones that don't match our Episode
        if movie['type'] == 'episode':
            episodes = []
            for sub in subs:
                data_obj = re.search(_re_season_episode, sub['release'])
                if data_obj:
                    data = data_obj.groupdict()
                    if int(data['episode']) == int(movie['episode']):
                        episodes.append(sub)
            subs = episodes

        subtitles = legendastv.rankSubtitles(movie, subs)
        if not subtitles:
            notify("No subtitles found for episode %d", int(movie['episode']))
            return

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
        archive = legendastv.downloadSubtitle(subtitles[0]['hash'], savedir)
        files = ft.extract_archive(archive, savedir, [".srt"])
        if len(files) > 1:
            # Damn those multi-file archives!
            notify("%s subtitles in archive" % len(files))

            # Build a new list suitable for comparing
            files = [dict(compare=dt.clean_string(os.path.basename(
                                                  os.path.splitext(f)[0])),
                          original=f)
                     for f in files]

            # Should we use file or dir as a reference?
            dirname_compare  = dt.clean_string(dirname)
            filename_compare = dt.clean_string(filename)
            if dt.get_similarity(dirname_compare , files[0]['compare']) > \
               dt.get_similarity(filename_compare, files[0]['compare']):
                result = dt.choose_best_by_key(dirname_compare,
                                               files, 'compare')
            else:
                result = dt.choose_best_by_key(filename_compare,
                                               files, 'compare')

            file = result['best']
            files.remove(file) # remove the chosen from list
            [os.remove(f['original']) for f in files] # delete the list
            file = result['best']['original'] # convert back to string
        else:
            file = files[0] # so much easier...

        newname = os.path.join(savedir, filename) + ".srt"
        #notify("Matching '%s'" % os.path.basename(file)) # enough notifications
        os.rename(file, newname)
        notify("DONE! Oba Rê!!")
        return True

    else:
        # Are you *sure* this movie exists? Try our interactive mode
        # and search for yourself. I swear I tried...
        notify("No subtitles found")
        return False
