import os
import argparse
from datetime import datetime
from flask_script import Manager
import numpy as np
import pickle

from server import music_graph_helper as mgh, song_helper, app
from server.exceptions import *

_cache_types = {'top_song_stats': {'version': 1}, 'cluster_index': {'version': 1}, 'cluster': {'version': 1},
                'genre_features': {'version': 1}, 'genre_affinity': {'version': 1}, 'scaler': {'version': 1}}


CacheCommand = Manager(usage='Perform music graph cache operations')


def _prepare_cache_key(key):
    # todo: use regexp replace instead of string
    return key.replace(':','_')


def _load_from_cache(cache_type, key):
    c_ct = _cache_types[cache_type]
    entry_name = key + '.' + cache_type
    path = app.config['USER_STORAGE_URI'] + entry_name
    if os.path.isfile(path):
        try:
            with open(path, 'br') as f:
                ct = pickle.load(f)
                if ct['version'] != c_ct['version']:
                    raise CacheRecordVersionMismatchException(ct['version'], c_ct['version'], entry_name)
                return ct['p'], ct['sn']
        except (pickle.PickleError, TypeError, EOFError):
            # delete file and raise
            os.remove(path)
            raise
    else:
        raise CacheEntryNotExistsException(key + cache_type)


def _save_to_cache(cache_type, key, sn, payload):
    ct = _cache_types[cache_type].copy()
    entry_name = key + '.' + cache_type
    ct['p'] = payload
    ct['sn'] = sn
    path = app.config['USER_STORAGE_URI'] + entry_name
    with open(path, 'bw') as f:
        pickle.dump(ct, f, protocol=4)


def _compute_global_objects():
    glob = mgh.init_songs_db()
    # load top songs and compute features
    top_song_features = mgh.load_song_features(song_helper.db_make_song_selector_top_songs())
    # will create scaler
    top_song_features, top_song_genres, glob.features_scaler = mgh.prepare_songs(top_song_features)
    glob.top_songs_f_min = np.min(top_song_features, axis=0)
    glob.top_songs_f_max = np.max(top_song_features, axis=0)
    mgh.G = glob
    glob.genre_features, glob.genre_sleepiness, glob.genre_wakefulness = \
        mgh.init_compute_genre_features(glob.genres, top_song_features, top_song_genres)

    return glob


def _update_global_cache(glob, sn):
    _save_to_cache('top_song_stats', 'top_songs_f_min', sn, glob.top_songs_f_min)
    _save_to_cache('top_song_stats', 'top_songs_f_max', sn, glob.top_songs_f_max)
    _save_to_cache('scaler', 'features_scaler', sn, glob.features_scaler)
    _save_to_cache('genre_features', 'genre_features', sn, glob.genre_features)
    _save_to_cache('genre_affinity', 'genre_sleepiness', sn, glob.genre_sleepiness)
    _save_to_cache('genre_affinity', 'genre_wakefulness', sn, glob.genre_wakefulness)


@CacheCommand.command
def update_global_cache():
    """Updates global objects cache"""
    print('computing global objects')
    glob = _compute_global_objects()
    sn = str(datetime.utcnow())
    print('saving global objects')
    _update_global_cache(glob, sn)
    print('global objects saved with sn=%s' % sn)


@CacheCommand.command
def update_sleep_clusters_cache():
    """Updates sleep clusters cache"""
    mgh.G = global_from_cache()
    sn = str(datetime.utcnow())
    for gid, sleep_clusters in mgh.init_compute_sleep_clusters():
        gname = mgh.G.genres[gid]
        print('saving sleep clusters for "%s"' % gname)
        _save_to_cache('cluster', 'sleep_' + gname, sn, sleep_clusters)
    print('global objects saved with sn=%s' % sn)


@CacheCommand.command
def update_wakeup_clusters_cache():
    """Updates wakeup clusters cache"""
    mgh.G = global_from_cache()
    sn = str(datetime.utcnow())
    for gid, wakeup_clusters in mgh.init_compute_wakeup_clusters():
        gname = mgh.G.genres[gid]
        print('saving wakeup clusters for "%s"' % gname)
        _save_to_cache('cluster', 'wakeup_' + gname, sn, wakeup_clusters)
    print('global objects saved with sn=%s' % sn)


@CacheCommand.command
def update_pop_clusters_cache():
    """Updates popular clusters cache"""
    mgh.G = global_from_cache()
    sn = str(datetime.utcnow())
    for gid, pop_clusters in mgh.init_compute_pop_clusters():
        gname = mgh.G.genres[gid]
        print('saving popular clusters for "%s"' % gname)
        _save_to_cache('cluster', 'pop_' + gname, sn, pop_clusters)
    print('global objects saved with sn=%s' % sn)


def get_genre_clusters(cluster_type, genre_id):
    gname = mgh.G.genres[genre_id]
    return _load_from_cache('cluster', cluster_type + '_' + gname)[0]


def global_from_cache():
    glob = mgh.init_songs_db()
    glob.top_songs_f_min, _ = _load_from_cache('top_song_stats', 'top_songs_f_min')
    glob.top_songs_f_max, _ = _load_from_cache('top_song_stats', 'top_songs_f_max')
    glob.features_scaler, _ = _load_from_cache('scaler', 'features_scaler')
    glob.genre_features, _ = _load_from_cache('genre_features', 'genre_features')
    glob.genre_sleepiness, _ = _load_from_cache('genre_affinity', 'genre_sleepiness')
    glob.genre_wakefulness, _ = _load_from_cache('genre_affinity', 'genre_wakefulness')
    return glob
