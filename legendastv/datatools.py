#!/usr/bin/python
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
# Utilities to manipulate data like strings, lists and dicts

import re
import difflib
import logging

from . import utils

log = logging.getLogger(__name__)


def fields_to_int(d, *keys):
    """ Helper function to cast several fields in a dict to int
        usage: int_fields(mydict, 'keyA', 'keyB', 'keyD')
    """
    for key in keys:
        if d[key] is not None:
            d[key] = int(d[key])


def get_similarity(text1, text2, ignorecase=True):
    """ Return a float in [0,1] range representing the similarity of 2 strings
    """
    if ignorecase:
        text1 = text1.lower()
        text2 = text2.lower()
    return difflib.SequenceMatcher(None, text1, text2).ratio()


def clean_string(text):
    text = re.sub(r"^\[.+?]"   ,"",text)
    text = re.sub(r"[][}{)(.,:_-]"," ",text)
    text = re.sub(r" +"       ," ",text).strip()
    return text


def filter_dict(d, keys=[], whitelist=True):
    """ Filter a dict, returning a copy with only the selected keys
        (or all *but* the selected keys, if not whitelist)
    """
    if keys:
        if whitelist:
            return dict([(k, v) for (k, v) in d.items() if k in keys])
        else:
            return dict([(k, v) for (k, v) in d.items() if k not in keys])
    else:
        return d


def print_dictlist(dictlist, keys=None, whitelist=True):
    """ Prints a list, an item per line """
    return "\n".join([repr(filter_dict(d, keys, whitelist))
                      for d in dictlist])


def choose_best_string(reference, candidates, ignorecase=True):
    """ Given a reference string and a list of candidate strings, return a dict
        with the candidate most similar to the reference, its index on the list
        and the similarity ratio (a float in [0, 1] range)
    """
    if ignorecase:
        reference_lower  = reference.lower()
        candidates_lower = [c.lower() for c in candidates]
        result = difflib.get_close_matches(reference_lower,
                                           candidates_lower,1, 0)[0]

        index = candidates_lower.index(result)
        best  = candidates[index]
        similarity = get_similarity(reference_lower, result, False)

    else:
        best = difflib.get_close_matches(reference, candidates, 1, 0)[0]
        index = candidates.index(best)
        similarity = get_similarity(reference, best, False)

    return dict(best = best,
                index = index,
                similarity = similarity)


def choose_best_by_key(reference, dictlist, key, ignorecase=True):
    """ Given a reference string and a list of dictionaries, compare each
        dict key value against the reference, and return a dict with keys:
        'best' = the dict whose key value was the most similar to reference
        'index' = the position of the chosen dict in dictlist
        'similarity' = the similarity ratio between reference and dict[key]
    """
    if ignorecase:
        best = choose_best_string(reference.lower(),
                                  [d[key].lower() for d in dictlist],
                                  ignorecase = False)
    else:
        best = choose_best_string(reference, [d[key] for d in dictlist], False)

    result = dict(best = dictlist[best['index']],
                  similarity = best['similarity'])
    utils.print_debug("Chosen best for '%s' in '%s': %s" % (reference, key, result))
    return result


def iter_find_in_dd(D, k, v):
    """ Given a dictionary of dictionaries D, find the inner dictionary(ies) d
        whose key k has value v, and yields a 2-tuple of outerkey K, innerdict d.
        f(D, k, v) => K, D[K] such as D[K][k] == v
        Note that all of D's inner dicts must contain the key k
    """
    for K, d in D.iteritems():
        if d[k] == v:
            yield K, d
