#!/usr/bin/python
# -*- coding: utf-8 -*-
#
#    Copyright (C) 2014 Rodrigo Silva (MestreLion) <linux@rodrigosilva.com>
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
# Miscellaneous utilities

import os
import dbus
import logging

from . import g

log = logging.getLogger(__name__)


def notify(body, *args, **kwargs):
    summary = kwargs.pop('summary', '')
    icon    = kwargs.pop('icon',    '')
    if kwargs:
        raise TypeError("invalid arguments for notify(): %s" % kwargs)

    logbody = body if not summary else " - ".join((summary, body))

    # Fallback for no notifications
    if not g.options['notifications']:
        log.notify(logbody, *args)
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

    if icon and os.path.isfile(icon):
        g.globals['notify_icon'] = icon # save for later
    app_icon    = g.globals['notify_icon']

    g.globals['notifier'].Notify(app_name, replaces_id, app_icon, summary,
                                 body % args, actions, hints, timeout)
    log.notify(logbody, *args)


def print_debug(text):
    log.debug('\n\t'.join(text.split('\n')))
