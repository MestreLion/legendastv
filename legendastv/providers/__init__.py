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

from __future__ import absolute_import

__all__ = ['providers']

providers = []


class Provider(object):
    pass


def _setup_providers():
    import pkgutil

    for importer, modname, ispkg in pkgutil.iter_modules(__path__):
        if not ispkg:
            __all__.append(modname)
            fullname = "%s.%s" % (__name__, modname)
            __import__(fullname, globals, locals)

    providers.extend(Provider.__subclasses__())


_setup_providers()
