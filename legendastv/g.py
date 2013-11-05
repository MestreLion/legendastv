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
# Global options, parameters and definitions

from __future__ import unicode_literals, absolute_import

import os
import ConfigParser
import logging

log = logging.getLogger(__name__)

globals = {

    'appname'   : __name__.split(".")[0],

    'apptitle'  : "Legendas.TV",

    'version'   : "1.0",

    'notifier'  : None,
}
globals.update({

    'appicon'   : os.path.abspath(
                    os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                 "..", globals['appname'] + ".png")),

    'cache_dir' : os.path.join(os.environ.get('XDG_CACHE_HOME') or
                               os.path.join(os.path.expanduser('~'), '.cache'),
                               globals['appname']),

    'config_dir': os.path.join(os.environ.get('XDG_CONFIG_HOME') or
                               os.path.join(os.path.expanduser('~'), '.config'),
                               globals['appname']),
})
globals.update({

    'notify_icon' : globals['appicon'],

    'config_file' : os.path.join(globals['config_dir'],
                                 globals['appname'] + ".ini"),

    'log_file'    : os.path.join(globals['cache_dir'],
                                 globals['appname'] + ".log"),
})

# These factory settings are also available at config file
options = {
    'login'         : "",
    'password'      : "",
    'debug'         : True,
    'cache'         : True,
    'similarity'    : 0.7,
    'notifications' : True,
}

def read_config():

    section = "Preferences"
    cp = ConfigParser.SafeConfigParser()

    if not os.path.exists(globals['config_file']):
        if not os.path.isdir(globals['config_dir']):
            os.makedirs(globals['config_dir'])
        cp.add_section(section)
        for option in options:
            cp.set(section, option, unicode(options[option]))

        with open(globals['config_file'], 'w') as f:
            cp.write(f)

        log.info("A blank config file was created at %s\n"
                 "Please edit it and fill in login and password before using"
                 " this module", globals['config_file'])

        return

    cp.read(globals['config_file'])

    if cp.has_section(section):
        for option in options:
            if   isinstance(options[option], bool ): get = cp.getboolean
            elif isinstance(options[option], int  ): get = cp.getint
            elif isinstance(options[option], float): get = cp.getfloat
            else                                   : get = cp.get

            try:
                options[option] = get(section, option)

            except ConfigParser.NoOptionError as e:
                log.warn("%s in %s", e, globals['config_file'])

            except ValueError as e:
                log.warn("%s in '%s' option of %s", e, option,
                         globals['config_file'])
