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

from __future__ import unicode_literals, absolute_import

import os, sys
import logging.handlers

from legendastv import g, filetools, legendastv

def run_demo():
    # API tests
    search = "gattaca"
    ltv = legendastv.LegendasTV(g.options['login'], g.options['password'])
    movies = ltv.getMovies(search)
    if movies:
        ltv.getMovieDetails(movies[0])
        ltv.getSubtitleDetails(ltv.getSubtitlesByText(search)[0]['hash'])

def setup_logging():

    # Use same logger as the package
    log = logging.getLogger(g.globals['appname'])

    # Console output (stderr)
    sh = logging.StreamHandler()

    # Rotating log file (10 x 1MB)
    fh = logging.handlers.RotatingFileHandler(g.globals['log_file'],
                                              maxBytes=2**20,
                                              backupCount=10,
                                              delay=True,)

    # Format them
    #format = '%(asctime)s %(name)-21s %(levelname)-6s %(message)s'
    format = '%(asctime)s %(levelname)-8s %(message)s'
    fmt = logging.Formatter(format)
    fh.setFormatter(fmt)
    sh.setFormatter(fmt)

    # Add them to logger
    log.addHandler(fh)
    log.addHandler(sh)

    return log


if __name__ == "__main__":

    log = setup_logging()

    g.read_config()

    if g.options['debug']:
        log.setLevel(logging.DEBUG)

    if not (g.options['login'] and g.options['password']):
        log.warn("Login or password is blank. You won't be able to access"
                 " Legendas.TV without it.\n"
                 "Please edit your config file at %s\n"
                 "and fill them in", g.globals['config_file'])

    # User selects a movie by filename...
    filename = (unicode(sys.argv[1], "utf-8")
                if len(sys.argv) > 1
                else os.path.expanduser("~/Videos/CSI/Season 12/"
                                        "CSI.S12E19.720p.HDTV.X264-DIMENSION.mkv"))

    try:
        if os.path.isdir(filename):
            # Its a dir, so log in just once and loop its files
            legendastv.notify("Logging in Legendas.TV")
            ltv = legendastv.LegendasTV()
            for root, subFolders, files in os.walk(filename):
                for video in files:
                    videofile = os.path.join(root, video)
                    if filetools.is_video(videofile):
                        legendastv.retrieve_subtitle_for_movie(videofile,
                                                               legendastv=ltv)

        else:
            legendastv.retrieve_subtitle_for_movie(filename)
    except Exception as e:
        log.critical(e, exc_info=1)
