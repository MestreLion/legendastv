import os
import sys
import logging


if __name__ == '__main__':
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from legendastv.providers.opensubtitles import (
    Osdb, videohash, videoinfo, OpenSubtitlesError
)


logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)


try:
    osdb = Osdb()
    osdb.ServerInfo()
    osdb.GetSubLanguages('pb')

    for path in sys.argv[1:]:
        if os.path.isfile(path):
            print path
            print videohash(path)
            for movie in videoinfo(path, osdb):
                print movie
            print
except OpenSubtitlesError as e:
    log.error(e)
