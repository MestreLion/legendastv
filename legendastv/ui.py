#!/usr/bin/python
# -*- coding: utf-8 -*-
#
#    Copyright (C) 2013 Rodrigo Silva (MestreLion) <linux@rodrigosilva.com>
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
# GUI classes and methods

from __future__ import unicode_literals, absolute_import

from gi.repository import Gtk

#from ..providers import opensubtitles
from legendastv.providers import opensubtitles

class MyWindow(Gtk.Window):

    def __init__(self):
        Gtk.Window.__init__(self, title="Hello World")
        self.connect("delete-event", Gtk.main_quit)
        self.set_border_width(10)

        vbox1 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(vbox1)

        hbox1 = Gtk.Box()
        vbox1.add(hbox1)

        grid = Gtk.Grid()
        hbox1.add(grid)

        for y, label in enumerate(["Language", "Title", "Season", "Episode"]):
            grid.attach(Gtk.Label(label), 0, y, 1, 1)

        lang_store = Gtk.ListStore(str, str)
        oss = opensubtitles.OpenSubtitles()
        languages = oss.getLanguages()
        for lang in sorted(languages)[:]:
            lang_store.append([languages[lang]['id'], languages[lang]['name']])

        cell = Gtk.CellRendererText()
        self.selLanguage = Gtk.ComboBox.new_with_model(lang_store)
        self.selLanguage.set_active(0)
        self.selLanguage.connect("changed", self.on_lang_changed)
        self.selLanguage.pack_start(cell, True)
        self.selLanguage.add_attribute(cell, "text", 1)
        
        grid.attach(self.selLanguage, 1, 0, 1, 1)

        self.txtTitle = Gtk.Entry(expand=True)
        grid.attach(self.txtTitle, 1, 1, 1, 1)

        self.txtSeason = Gtk.Entry(expand=True)
        grid.attach(self.txtSeason, 1, 2, 1, 1)

        self.txtEpisode = Gtk.Entry(expand=True)
        grid.attach(self.txtEpisode, 1, 3, 1, 1)

        vbox3 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        hbox1.add(vbox3)

        self.btnSearchByHash = Gtk.Button("Search by Hash")
        vbox3.add(self.btnSearchByHash)

        self.btnSearchByName = Gtk.Button("Search by Name")
        vbox3.add(self.btnSearchByName)

        store = Gtk.ListStore(str)
        self.lstSubtitles = Gtk.TreeView(store)
        vbox1.add(self.lstSubtitles)

        hbox2 = Gtk.Box()
        vbox1.add(hbox2)

        button = Gtk.Button(label="Close")
        button.connect("clicked", self.on_close_clicked)
        hbox2.add(button)


    def on_close(self):
        Gtk.main_quit()


    def on_close_clicked(self):
        self.on_close()


    def on_lang_changed(self, widget):
        tree_iter = widget.get_active_iter()
        if tree_iter is not None:
            model = widget.get_model()
            langid, name = model[tree_iter]
            print "Selected: language=%s (%s)" % (langid, name)


def main():
    win = MyWindow()
    win.show_all()
    Gtk.main()

if __name__ == "__main__":
    main()
