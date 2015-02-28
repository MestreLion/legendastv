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
# Miscellaneous file-handling functions

import os
import zipfile
import rarfile
import logging

from . import datatools as dt
from . import g

log = logging.getLogger(__name__)
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)


# Most common video file extensions. NOT meant as a comprehensive list!
# Listed here for performance reasons only,  to avoid a perhaps expensive mimetype detection
VIDEO_EXTS = {'avi', 'm4v', 'mkv', 'mp4', 'mpg', 'mpeg', 'ogv', 'rmvb', 'wmv', 'ts'}

# Extensions that are not properly detected as "video/" mimetype
VIDEO_EXTS_EXTRA = {}

try:

    from gi import Repository
    if not Repository.get_default().enumerate_versions('Gio'):
        raise ImportError
    from gi.repository import Gio
    log.debug("using Gio")

    VIDEO_EXTS_EXTRA = {'mpv', 'ts', 'wm', 'wx', 'xvid'}

    def mimetype(path):
        ''' Mimetype of a file, determined by its extension and, in case of
            extensionless files, its initial content (1KB read).
            Return 'application/octet-stream' for unknown types and non-files:
            directories, broken symlinks, path not found, access denied.
        '''
        mime = Gio.content_type_get_mime_type(Gio.content_type_guess(filename=path, data=None)[0])
        if extension(path):
            return mime

        try:
            with open(path, 'rb') as f:
                return Gio.content_type_guess(filename=None, data=f.read(1024))[0]
        except IOError:
            return mime  # most likely access denied or file not found

    # .60d    application/octet-stream
    # .ajp    application/octet-stream
    # .asx    audio/x-ms-asx
    # .avchd    application/octet-stream
    # .bik    application/octet-stream
    # .bin    application/octet-stream
    # .bix    application/octet-stream
    # .box    application/octet-stream
    # .cam    application/octet-stream
    # .cue    application/x-cue
    # .dat    application/octet-stream
    # .dif    application/octet-stream
    # .dl    application/octet-stream
    # .dmf    application/octet-stream
    # .dvr-ms    application/octet-stream
    # .evo    application/octet-stream
    # .flic    application/octet-stream
    # .flx    application/octet-stream
    # .gl    application/octet-stream
    # .gvi    application/octet-stream
    # .gvp    text/x-google-video-pointer
    # .h264    application/octet-stream
    # .lsf    application/octet-stream
    # .lsx    application/octet-stream
    # .m1v    application/octet-stream
    # .m2p    application/octet-stream
    # .m2v    application/octet-stream
    # .m4e    application/octet-stream
    # .mjp    application/octet-stream
    # .mjpeg    application/octet-stream
    # .mjpg    application/octet-stream
    # .movhd    application/octet-stream
    # .movx    application/octet-stream
    # .mpa    application/octet-stream
    # .mpv    application/octet-stream
    # .mpv2    application/octet-stream
    # .mxf    application/mxf
    # .nut    application/octet-stream
    # .ogg    audio/ogg
    # .omf    application/octet-stream
    # .ps    application/postscript
    # .ram    application/ram
    # .rm    application/vnd.rn-realmedia
    # .rmvb    application/vnd.rn-realmedia
    # .swf    application/x-shockwave-flash
    # .ts    text/vnd.trolltech.linguist
    # .vfw    application/octet-stream
    # .vid    application/octet-stream
    # .video    application/octet-stream
    # .vro    application/octet-stream
    # .wm    application/octet-stream
    # .wmx    audio/x-ms-asx
    # .wrap    application/octet-stream
    # .wvx    audio/x-ms-asx
    # .wx    application/octet-stream
    # .x264    application/octet-stream
    # .xvid    application/octet-stream


except ImportError:

    import mimetypes
    log.debug("using Lib/mimetypes")

    mimetypes.init()

    VIDEO_EXTS_EXTRA = {'divx', 'm2ts', 'mpv', 'ogm', 'rmvb', 'ts', 'wm', 'wx', 'xvid'}

    def mimetype(path):
        ''' Mimetype of a file, determined by its extension.
            Return 'application/octet-stream' for unknown types and non-files:
            directories, broken symlinks, path not found, access denied.
        '''
        return mimetypes.guess_type(path, strict=False)[0] or "application/octet-stream"

    # .3g2    None
    # .3gp2    None
    # .3gpp    None
    # .60d    None
    # .ajp    None
    # .avchd    None
    # .bik    None
    # .bin    application/octet-stream
    # .bix    None
    # .box    None
    # .cam    None
    # .cue    None
    # .dat    application/x-ns-proxy-autoconfig
    # .divx    None
    # .dmf    None
    # .dvr-ms    None
    # .evo    None
    # .flc    None
    # .flic    None
    # .flx    None
    # .gvi    None
    # .gvp    None
    # .h264    None
    # .m2p    None
    # .m2ts    None
    # .m2v    None
    # .m4e    None
    # .m4v    None
    # .mjp    None
    # .mjpeg    None
    # .mjpg    None
    # .moov    None
    # .movhd    None
    # .movx    None
    # .mpv2    None
    # .mxf    application/mxf
    # .nsv    None
    # .nut    None
    # .ogg    audio/ogg
    # .ogm    None
    # .omf    None
    # .ps    application/postscript
    # .ram    audio/x-pn-realaudio
    # .rm    audio/x-pn-realaudio
    # .rmvb    None
    # .swf    application/x-shockwave-flash
    # .vfw    None
    # .vid    None
    # .video    None
    # .viv    None
    # .vivo    None
    # .vob    None
    # .vro    None
    # .wrap    None
    # .wx    None
    # .x264    None
    # .xvid    None


def is_video(path):
    ''' Return True if path should be considered a video file, False otherwise.
        Determined by both file extension and its mimetype.
    '''
    ext = extension(path)
    if ext in VIDEO_EXTS or ext in VIDEO_EXTS_EXTRA:
        return True

    mimes = ['x-ms-asx',                                   # MS Windows Media Player - asx, wmx, wvx
             'ram', 'vnd.rn-realmedia', 'x-pn-realaudio',  # RealAudio/Media - ram, rm, rmvb
             'x-shockwave-flash',                          # Adobe Flash Player - swf
             ]
    ftype, mime = mimetype(path).split('/')
    return ftype == 'video' or mime in mimes


def extension(path):
    ''' Normalized extension for a filename: lowercase and without leading '.'
        Can be empty. Does not consider POSIX hidden files to be extensions.
        Example: extension('A.JPG') -> 'jpg'
    '''
    return os.path.splitext(path)[1][1:].lower()


def extract_archive(archive, path=None, extlist=[], keep=True, overwrite=False):
    """ Extract all files from a zip or rar archive
        - archive: the archive filename (with path)
        - path: the extraction folder, by default the archive path without extension
        - extlist: list or a comma-separated string of file extensions (excluding the ".")
        - keep: if False, archive is deleted after succesful extraction
        - overwrite: if false ans path exists, will skip extraction and read path contents
        return: a list of extracted filenames (with path) matching extlist,
            or all extracted files if extlist is empty
    """

    af = ArchiveFile(archive)
    if not af:
        log.error("File is not a supported archive format")
        return

    log.debug("%d files in archive '%s': %r",
              len(af.namelist()), os.path.basename(archive), af.namelist())

    if path is None:
        path = os.path.splitext(archive)[0]

    if overwrite or not os.path.exists(path):
        safemakedirs(path)
        af.extractall(path)

    # eliminates invalid  characters for the current filesystem encoding
    safepath(path)

    if isinstance(extlist, basestring):
        extlist = extlist.split(",")

    outputfiles = []
    for root, _, files in os.walk(path):
        for name in files:
            filepath = os.path.join(root, name)
            ext = os.path.splitext(name)[1][1:].lower()

            if not extlist or ext in extlist:
                outputfiles.append(filepath)

            elif ext in ['zip', 'rar']:
                outputfiles.extend(extract_archive(filepath,
                                                   extlist=extlist,
                                                   keep=True,
                                                   overwrite=False))

    af.close()

    if not keep:
        try:
            os.remove(archive)
        except IOError as e:
            log.error(e)

    log.info("%d extracted files in '%s', filtered by %s\n\t%s",
             len(outputfiles), archive, extlist, dt.print_dictlist(outputfiles))
    return outputfiles


def ArchiveFile(filename):
    """ Pseudo class (hence the Case) to wrap both rar and zip handling,
        since they both share almost identical API
        usage:  myarchive = ArchiveFile(filename)
        return: a RarFile or ZipFile instance (or None), depending on
                <filename> content
    """
    if   rarfile.is_rarfile(filename):
        return rarfile.RarFile(filename, mode='r')

    elif zipfile.is_zipfile(filename):
        return zipfile.ZipFile(filename, mode='r')

    else:
        return None


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        log.critical("Missing argument\nUsage: %s FILE", __file__)
        sys.exit(1)

    for path in sys.argv[1:]:
        if os.path.isfile(path):
            print
            print os.path.realpath(path)
            print mimetype(path)
            print "%svideo" % ("" if is_video(path) else "NOT ")


def safemakedirs(path):
    try:
        os.makedirs(path, 0700)
    except OSError as e:
        if e.errno != 17:  # File exists
            raise

def safepath(path):
    """ Iterates through all the files and sub directories in order to detect invalid
        characters. When a file name or directory name contains an invalid character
        it's renamed to be compliant with the filesystem encoding.
    """
    encoded_path = path.encode(g.filesystem_encoding)
    for dirname, dirnames, filenames in os.walk(encoded_path):
        for subdirname in dirnames:
            safepathname(dirname, subdirname)
        for filename in filenames:
            safepathname(dirname, filename)

def safepathname(path, name):
    """ Encoding detection: UTF-8, CP850 and ISO-8859-15
        If the existing name is encoded in any of the specified encodings, 
        the file/folder is renamed to be compliant with the filesystem encoding
    """
    path_encoding = None
    for i in range(len(name)):
        current_char = name[i]
        if len(name) != 1 and i < (len(name) - 1):
            next_char = name[i + 1]
            # Detects UTF-8: we need to always check 2 chars to detect UTF-8 special characters
            # 1st char: 0xC2-0xC3
            # 2nd char: 0x80-0xFF
            if ((current_char == '\xC2' or current_char == '\xC3') and 
                (next_char >= '\x80' or next_char <= '\xFF')):
                path_encoding = 'UTF-8'
                break;

        # Detects CP850: 0x80-0xA5
        if current_char >= '\x80' and current_char <= '\xA5':
            path_encoding = 'CP850'
            break;
        # Detects ISO-8859-15: 0xA6-0xFF
        elif current_char >= '\xA6' and current_char <= '\xFF':
            path_encoding = 'ISO-8859-15'
            break;
    
    if (path_encoding and g.filesystem_encoding != path_encoding):
        rename_invalid_paths(path, name, path_encoding)

def rename_invalid_paths(path, name, name_encoding):
    """ Re-encode the file/folder name to the filesystem encoding
    """
    safe_name = name.decode(name_encoding)
    safe_name = safe_name.encode(g.filesystem_encoding)
    safe_full_name = os.path.join(path, safe_name)
    os.rename(os.path.join(path, name), safe_full_name)
