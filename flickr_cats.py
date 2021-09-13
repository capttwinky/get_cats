#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#

import json
import os
from random import choice, gauss, sample, randint
from datetime import datetime
import re
from itertools import cycle
import gzip
from functools import wraps
from typing import Callable
import time

import flickr_api

## Only needed if you are generating adjtives, cf: https://www.nltk.org/data.html
# from nltk.corpus import brown

## Only needed if you are doing translations, cf: https://py-googletrans.readthedocs.io/en/latest/
# from googletrans import Translator

TRANS_TARGETS=('en', 'fr', 'de', 'it', 'es',)

def get_adjs():
    mwrds = brown.tagged_words(
        categories=brown.categories(),
        tagset='universal')
    return tuple(i[0] for i in mwrds if i[1] == 'ADJ')


def RateLimited(min_pause: int, max_pause:int) -> Callable:
    #minInterval = period / float(count)
    interval_gen = gen_pause_interval(min_pause, max_pause)
    def decorate(func):
        lastTimeCalled = None
        def rateLimitedFunction(*args,**kargs):
            nonlocal lastTimeCalled
            nonlocal interval_gen
            if lastTimeCalled:
                leftToWait = next(interval_gen)-(time.time()-lastTimeCalled)
                if leftToWait>0:
                    time.sleep(leftToWait)
            ret = func(*args,**kargs)
            lastTimeCalled = time.time()
            return ret
        return rateLimitedFunction
    return decorate

def gen_pause_interval(min_pause:float, max_pause:float)->float:
    prange = (max_pause-min_pause)
    median = min_pause+prange/2
    bin_step = prange/10
    while True:
        yield (bin_step*gauss(0,1))+median

def make_tags(items, rnd_choices):
    for mwrd in sample(items, len(items)):
        yield '{} {}'.format(mwrd, choice(rnd_choices))

@RateLimited(min_pause=10, max_pause=20)
def _get_translation(tag_in, destination):
    if not getattr(_get_translation, 'T'):
        _get_translation.T = Translator()
    try:
        mresp = _get_translation.T.translate(tag_in, destination)
    except json.JSONDecodeError as e:
        raise UserWarning('google issues :-(')
    return mresp.text

def translate_tag(tag_in, destination):
    tr = tag_in if destination == 'eng' else _get_translation(tag_in, destination)
    return ','.join(tr.split())

def main():
    output_dir = os.path.expanduser('./cat_photos')
    if os.path.exists('adjlist.gz'):
        with gzip.open('adjlist.gz') as ofile:
            adjs = ofile.read().decode().split()
    else:
        adjs = get_adjs()

    # ended up not needing this, but it you might
    # cat_tags = (translate_tag(t.lower(), choice(TRANS_TARGETS)) for t in make_tags(adjs, ('cat', 'kitten',)))
    cat_tags = tuple('{},{}'.format(adj.lower(), choice(('cat','kitty','kitten','kat', ))) for adj in sample(adjs,100))

    with open(os.path.expanduser('./.flickr_api')) as ofile:
        flickr_api.set_keys(*json.load(ofile))

    max_len_ctype = 0
    to_get = 100
    total_tries = 300
    remaining_tries = int(total_tries)
    photo_search=set()
    for ctype in cat_tags:
        cat_photos = list(flickr_api.Photo.search(
                               tags=ctype,
                               tag_mode='all',
                               license='1,2,3,4,5,6,7,8,9,10',
                               content_type=1,
                               media='photos',
                               sort='interestingness-desc',))
        if cat_photos:
            print(ctype, len(cat_photos))
            photo_search.update((ctype, cp) for cp in cat_photos)
            if len(ctype) > max_len_ctype:
                max_len_ctype = len(ctype)
            if len(photo_search) >= total_tries:
                break
        else:
            print(ctype)

    if not os.path.exists(output_dir):
        os.mkdir(output_dir)
    existing_img_names = {p.partition('.')[0] for p in os.listdir(output_dir)
        if p.endswith('.jpg')}

    replace_characters = re.compile(r' ')
    nonpath_characters = re.compile(r'[^\w\-_]')

    ctype_count = {}
    photo_search = list(photo_search)
    while to_get and remaining_tries and photo_search:
        ctype, photo = photo_search.pop(randint(0,len(photo_search)-1))
        pname = '{}-{}'.format(datetime.strptime(
            photo.taken, '%Y-%m-%d %H:%M:%S').strftime('%y%m%d%H%M%S'),
            nonpath_characters.sub('',replace_characters.sub('_',photo.title)))[:150]
        if pname not in existing_img_names:
            print(('{:<4}{:<'+str(max_len_ctype)+'} {}\t{}').format(
                to_get, ctype, pname, remaining_tries))
            try:
                photo.save(os.path.join(output_dir,pname), 'Medium')
            except flickr_api.FlickrError as e:
                print(e)
                remaining_tries -= 1
                continue
            ctype_count[ctype] = ctype_count.get(ctype,0)+1
            to_get -= 1
        else:
            remaining_tries -= 1

    print(ctype_count)

if __name__ == '__main__':
    main()
