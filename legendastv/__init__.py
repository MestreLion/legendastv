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
# Package initialization

__author__  = 'MestreLion <linux@rodrigosilva.com>'
__version__ = '0.1'
__all__     = []

import logging

from . import g

def _setup_logging():

    # "Main" logger for the project will be package's name
    log = logging.getLogger(__name__)

    # Be a well-behaved library and use only NullHandler
    log.addHandler(logging.NullHandler())

    # Add a custom level for notifications, between INFO and WARNING
    _NOTIFY = (25, "NOTIFY")
    logging.addLevelName(_NOTIFY[0], _NOTIFY[1])
    def notify(self, message, *args, **kws):
        self._log(_NOTIFY[0], message, args, **kws) # args, not *args
    logging.Logger.notify = notify


_setup_logging()