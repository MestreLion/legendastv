#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# legendastv - Legendas.TV Subtitle Downloader
# An API for Legendas.TV movie/TV series subtitles website
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
# When used as a package, provides several methods to log in, search for movies
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
# - Make a Windows/OSX port possible: cache and config dirs, unrar lib,
#   notifications
# - Create a suitable workflow for TV Series (seasons, episodes)

import os, sys
import logging.handlers

from legendastv import g, legendastv

if __name__ == "__main__":

    log = logging.getLogger(g.globals['appname'])
    fh = logging.handlers.RotatingFileHandler(g.globals['log_file'],
                                              maxBytes=2**20,
                                              backupCount=10,
                                              delay=True,)
    fh.setFormatter(logging.Formatter(logging.BASIC_FORMAT))
    log.addHandler(fh)
    log.addHandler(logging.StreamHandler())

    g.read_config()


    if g.options['debug']:
        log.setLevel(logging.DEBUG)

    if not (g.options['login'] and g.options['password']):
        log.warn("Login or password is blank. You won't be able to access"
                 " Legendas.TV without it.\n"
                 "Please edit your config file at %s\n"
                 "and fill them in", g.globals['config_file'])

    # User selects a movie by filename...
    try:
        usermovie = unicode(sys.argv[1], "utf-8")
    except:
        usermovie = os.path.expanduser("~/Videos/Lockout.UNRATED.720p.BluRay.x264-BLOW [PublicHD]/"
                                       "Lockout.UNRATED.720p.BluRay.x264-BLOW.PublicHD.mkv")

    if usermovie:
        try:
            legendastv.retrieve_subtitle_for_movie(usermovie)
        except Exception as e:
            legendastv.print_debug(repr(e))
            raise

    # API tests
    search = "gattaca"
    ltv = legendastv.LegendasTV(g.options['login'], g.options['password'])
    movies = ltv.getMovies(search)
    if movies:
        ltv.getMovieDetails(movies[0])
        ltv.getSubtitleDetails(ltv.getSubtitlesByText(search)[0]['hash'])
