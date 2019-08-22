import os
import sys
import logging


if __name__ == '__main__':
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import legendastv.datatools as dt
from legendastv.utils import print_debug
from legendastv.providers.opensubtitles import (
    OpenSubtitles, videohash, videoinfo, OpenSubtitlesError
)

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)


try:
    osdb = OpenSubtitles()
    osdb.ServerInfo()
    osdb.GetSubLanguages('pb')

    for path in sys.argv[1:]:
        if os.path.isfile(path):
            vhash = videohash(path)
            print
            print path
            print vhash
            osdb.getMovies(os.path.basename(path))
            titles = videoinfo(path, osdb)
            subs = osdb.getSubtitles(lang='en', vinfo=titles, vpath=path)
            print_debug(dt.print_dictlist(subs))
            for sub in subs:
                pass

except OpenSubtitlesError as e:
    log.error(e)
except KeyboardInterrupt:
    pass
