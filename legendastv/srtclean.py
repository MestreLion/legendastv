# -*- coding: utf-8 -*-
#
#    Copyright (C) 2014 Rodrigo Silva (MestreLion) <linux@rodrigosilva.com>
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

'''Tool to clean up SRT subtitles removing ads and misplaced credits'''

import os
import argparse
import logging
import shutil

#import chardet  # Ubuntu: python-chardet, required by pysrt

# There's 3 different `magic` modules, all wrappers to libmagic, with different API:
# - Debian/Ubuntu: python-magic (from `file` source package, https://github.com/file/file)
# - Pypi: python-magic (weird API, https://github.com/ahupp/python-magic)
# - Pypi: filemagic (modern API, well-documented. https://github.com/aliles/filemagic)
import magic
import pysrt  # pypi: pysrt / Ubuntu (14.04 onwards): python-pysrt

from . import g


log = logging.getLogger(__name__)


class ParseError(Exception):
    pass


def parseargs(argv=None):
    parser = argparse.ArgumentParser(
        description='Clean subtitles deleting items that matches entries in blacklist file. '
            "Useful to remove ads and misplaced credits"
    )

    parser.add_argument('--quiet', '-q', dest='loglevel',
                        action="store_const", const=logging.WARNING, default=logging.INFO,
                        help='suppress informative messages and summary statistics.')

    parser.add_argument('--verbose', '-v', dest='loglevel',
                        action="store_const", const=logging.DEBUG,
                        help='print additional information for each processed file. '
                        'Overwrites --quiet.')

    parser.add_argument('--recursive', '-r',
                        action="store_true", default=False,
                        help='recurse inside directories.')

    parser.add_argument('--input-encoding', '-e', dest="encoding",
                        help='encoding used in subtitles, if known. By default tries to autodetect encoding.')

    parser.add_argument('--input-fallback-encoding', '-f', dest="fallback",
                        default="windows-1252",
                        help='fallback encoding to read subtitles if encoding autodetection fails. [Default: %(default)s]')

    parser.add_argument('--convert', '-c', dest="output_encoding",
                        help='convert subtitle encoding. By default uses same encoding as input.')

    parser.add_argument('--in-place', '-i',
                        action="store_true", default=False,
                        help="Overwrite original file instead of outputting to standard output")

    parser.add_argument('--no-backup', '-B', dest="backup",
                        action="store_false", default=True,
                        help="When using --in-place, do not create a backup file.")

    parser.add_argument('--no-rebuild-index', '-I', dest="rebuild_index",
                        action="store_false", default=True,
                        help="do not rebuild subtitles indexes after removing items. "
                            "Resulting SRT will not be strictly valid, although it will work in most players. "
                            "Useful when debugging and comparing original and modified subtitles")

    parser.add_argument('--blacklist', '-b', dest="blacklistfile",
                        default=os.path.join(g.globals['config_dir'], "%s_blacklist.txt" % __name__.split('.')[-1]),
                        help="Blacklist file path. [Default: %(default)s]")

    parser.add_argument('paths',
                        nargs='+',
                        help='SRT file(s) or dir(s) to modify')

    return parser.parse_args(argv)


def find_subtitles(paths, recursive=False):
    def ext(path):
        return os.path.splitext(path)[1][1:].lower()

    for path in paths:
        if os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                if not recursive:
                    del dirs[:]
                for file in files:
                    if ext(file) == 'srt':
                        yield os.path.join(root, file)
        else:
            if ext(path) == 'srt':
                yield path
            else:
                log.warn("Not an SRT file: '%s'", path)


def detect_encoding(filename, fallback=None):
    encoding = ""

    # Debian's python-magic, from `file` upstream
    if hasattr(magic.Magic, "file"):
        ms = magic.open(magic.MAGIC_MIME_ENCODING)
        ms.load()
        encoding = ms.file(filename)
        ms.close()

    # Pypi's python-magic
    elif hasattr(magic.Magic, "from_file"):
        ms = magic.Magic(mime_encoding=True)
        encoding = ms.from_file(filename)
        del ms  # force automatic close()

    # filemagic
    else:
        with magic.Magic(flags=magic.MAGIC_MIME_ENCODING) as m:
            encoding = m.id_filename(filename)

    if encoding and encoding not in ['unknown-8bit', 'binary']:
        log.debug("Auto-detected encoding: '%s'", encoding)
        return encoding

    #chardet is unreliable to detect Latin-1 (AKA ISO-8859-1/15, cp1252, windows-1252, etc)
    #with open(filename, 'rb') as fp:
    #    return chardet.detect(fp.read()).get('encoding')

    log.debug("Encoding auto-detection failed, using fallback: '%s'", fallback)
    return fallback


def open_subtitle(filename, encoding=None, fallback=None):
    '''Wrapper to pysrt.open() with encoding auto-detection
        could eventually be replaced with another parser to avoid this encoding madness
    '''
    if encoding is None:
        encoding = detect_encoding(filename, fallback=fallback)
    else:
        log.debug("Encoding: '%s'", encoding)

    try:
        return pysrt.open(filename, encoding=encoding)
    except UnicodeDecodeError as e:
        raise ParseError("error using encoding '%s': %r" % (encoding, e))


def main(argv=None):
    args = parseargs(argv)
    logging.basicConfig(level=args.loglevel, format='[%(levelname)-5s] %(message)s')
    log.debug("Arguments: %s", args)

    for path in find_subtitles(args.paths, recursive=args.recursive):
        log.info("Processing subtitle: '%s'", path)
        modified = False
        try:
            subs = open_subtitle(path, encoding=args.encoding, fallback=args.fallback)
        except ParseError as e:
            log.error("Could not open '%s': %s", path, e)
            continue

        modified = clean(subs, args.blacklistfile, rebuild_index=args.rebuild_index)

        if modified:
            if args.in_place:
                if args.backup:
                    shutil.copy(path, "%s.%s.bak" % (path, __name__.split('.')[-1]))
                subs.save(encoding=args.output_encoding)
            else:
                for sub in subs:
                    print unicode(sub).encode(args.output_encoding or subs.encoding)


def clean(subs, blacklistfile, rebuild_index=True):
    try:
        with open(blacklistfile, 'r') as fp:
            blacklist = fp.read().decode('utf-8').strip().split('\n\n')
    except IOError:
        return

    deleted = []
    for sub in reversed(subs):
        for text in blacklist:
            if text.replace('\\n', '\n').lower() in sub.text.lower():
                deleted.append(sub)
                subs.remove(sub)

    if deleted:
        log.info("%d items deleted", len(deleted))
        for item in reversed(deleted):
            log.debug(unicode(item).replace('\n', '\t').strip())
        if rebuild_index:
            subs.clean_indexes()

    return bool(deleted)