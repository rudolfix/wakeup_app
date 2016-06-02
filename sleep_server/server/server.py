import inspect
import os
import time
import random
from flask import json, request
import base64
from functools import wraps
import logging
from logging.handlers import RotatingFileHandler

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
os.sys.path.insert(0, parentdir)
from common.user_base import UserBase
from common import spotify_helper
from server import app, db, song_helper, echonest_helper, user_library, music_graph_helper as mgh, cache, mq
from common.exceptions import ApiException, LibraryNotExistsException, LibraryNotResolvedException
from common.common import possible_list_types


def require_user(f):
    @wraps(f)
    def _wrap(*args, **kwargs):
        user = UserBase.from_jsons(
            str(base64.decodebytes(request.headers.get('Authorization').encode('ascii')), 'ascii'))
        return f(user, *args, **kwargs)

    return _wrap


@app.route('/library/<user_id>', methods=['POST'])
@require_user
def library_update(user, user_id):
    library = user_library.load_library(user_id)
    # create empty library before returning
    if library.is_new:
        user_library.save_library(library)
    body = json.dumps({'user_id': user_id, 'user': user.to_jsons()})
    mq.send_update_message(body)
    return 'queued', 202  # accepted


@app.route('/library/<user_id>')
def library_get_props(user_id):
    library = user_library.load_library(user_id)
    if library.is_new:
        raise LibraryNotExistsException(user_id)
    return json.jsonify(result={'created_at': library.created_at, 'resolved_at': library.resolved_at,
                                'is_resolved': library.is_resolved,
                                'can_be_updated': library.can_be_updated})


@app.route('/library/<user_id>', methods=['DELETE'])
def library_delete(user_id):
    user_library.delete_library(user_id)
    return 'deleted', 204


@app.route('/library/<user_id>/playlists')
@app.route('/library/<user_id>/playlists/<playlist_type>')
def library_list_playlists(user_id, playlist_type=None):
    library = user_library.load_library(user_id)
    if library.is_new:
        raise LibraryNotExistsException(user_id)
    if not library.is_resolved:
        raise LibraryNotResolvedException(user_id)
    lib_song_features, _ = mgh.load_user_library_song_features(library)
    lib_song_features, _, _ = mgh.prepare_songs(lib_song_features, mgh.G.features_scaler)
    add_pl_item = lambda plid, n, card, pref: {'plid': plid, 'name': n, 'card': card, 'pref': pref}
    rv = {}
    for pt in [pt for pt in possible_list_types if playlist_type is None or playlist_type == pt]:
        if pt == 'fall_asleep':
            rv[pt] = []
            top_sleepys, _ = mgh.compute_sleep_genres(lib_song_features, library.artists)
            for gid, prevalence, sleepiness, user_pref in top_sleepys:
                name = 'based on %s with %d%% sleepiness' % (mgh.G.genres[gid], int(sleepiness*100))
                # print('%s(%i): %f%% affinity:%f pref:%f' % (name, gid, 100*prevalence, 100*sleepiness, user_pref))
                rv[pt].append(add_pl_item(gid, name, prevalence, user_pref))
        if pt == 'wake_up':
            rv[pt] = []
            top_wakeful, _ = mgh.compute_wakeup_genres(lib_song_features, library.artists)
            for gid, prevalence, wakefulness, user_pref in top_wakeful:
                name = 'ends on %s with %d%% wakefulness' % (mgh.G.genres[gid], int(wakefulness*100))
                # print('%s(%i): %f%% affinity:%f pref:%f' % (name, gid, 100*prevalence, 100*wakefulness, user_pref))
                rv[pt].append(add_pl_item(gid, name, prevalence, user_pref))
    return json.jsonify(result=rv)


@app.route('/library/<user_id>/playlists/<playlist_type>', methods=['POST', 'PUT'])
@app.route('/library/<user_id>/playlists/<playlist_type>/<int:playlist_id>', methods=['POST', 'PUT'])
@require_user
def create_playlist(user, user_id, playlist_type, playlist_id=None):
    library = user_library.load_library(user_id)
    if library.is_new:
        raise LibraryNotExistsException(user_id)
    if not library.is_resolved:
        raise LibraryNotResolvedException(user_id)
    # get desired playlist length
    desired_length = int(request.values.get('desired_length'))
    # load user library content
    lib_song_features, _ = mgh.load_user_library_song_features(library)
    lib_song_features, _, _ = mgh.prepare_songs(lib_song_features, mgh.G.features_scaler)
    pl_tracks, exact_duration = None, None
    if playlist_type == 'fall_asleep':
        if playlist_id is None:
            # when playlist id is not present choose genre where user has most preferences
            top_sleepys, _ = mgh.compute_sleep_genres(lib_song_features, library.artists)
            # todo: if less than N sleepy clusters just add a few sleepy clusters we like or are close in genre graph
            playlist_id = user_library.get_best_playlist_id(playlist_type, library, top_sleepys)
        # get genre clusters from cache
        sleep_clusters = cache.get_genre_clusters('sleep', playlist_id)
        # may have many clusters, select one
        cluster = sleep_clusters[random.randint(0,len(sleep_clusters)-1)]
        # get playlist with selected length
        pl_song_features, _ = mgh.get_random_song_slice_with_length(cluster[2], desired_length, 0.3)
        # returns list of spotify ids and duration
        _, _, r_m = song_helper.prepare_playable_tracks(user, [int(f[mgh._f_song_id_i]) for f in
                                                        pl_song_features])
        # trim playlist to exact length
        pl_tracks, exact_duration = mgh.trim_song_slice_length(r_m, pl_song_features, desired_length)
    if playlist_type == 'wake_up':
        if playlist_id is None:
            # when playlist id is not present choose genre where user has most preferences
            top_wakeup, _ = mgh.compute_wakeup_genres(lib_song_features, library.artists)
            # todo: if less than wakeup clusters use spotify recommend and skip all further logic
            playlist_id = user_library.get_best_playlist_id(playlist_type, library, top_wakeup)
        # get most wakeful songs
        wakeup_genres, wakeup_song_features = mgh.compute_wakeup_genres(lib_song_features, library.artists)
        sleep_genres, _ = mgh.compute_sleep_genres(lib_song_features, library.artists)
        pop_genres, _ = mgh.compute_popular_genres(lib_song_features, library.artists)
        # cut lowest 20% genres, typically crap you not remember
        pop_genres = pop_genres[:int(-len(pop_genres)*0.2)]
        wakeup_songs = mgh.generate_wakeup_playlist(playlist_id, wakeup_song_features, lib_song_features,
                                                    sleep_genres, pop_genres, int(desired_length + 0.5*desired_length))
        _, _, rm = song_helper.prepare_playable_tracks(user, [int(f[mgh._f_song_id_i]) for f in wakeup_songs])
        pl_tracks, exact_duration = mgh.trim_song_slice_length_by_acoustics(rm, wakeup_songs, desired_length,
                                                                            mgh._sound_energy_dist)

    return json.jsonify(result={playlist_type: {'duration_ms': exact_duration, 'tracks': pl_tracks}})


@app.errorhandler(ApiException)
def handle_api_error(e):
    app.logger.exception(e)
    return json.jsonify(_make_error_dict(e, e.status_code)), e.status_code


@app.errorhandler(Exception)
def handle_error(e):
    app.logger.exception(e)
    return json.jsonify(_make_error_dict(e, 500)), 500


@app.teardown_request
def teardown_request(exception):
    if exception:
        db.session.rollback()
    db.session.remove()


def _make_error_dict(e, status_code):
    return {'error': {'status': status_code, 'code': e.__class__.__name__, 'message': str(e)}}


def init_logging():
    handler = RotatingFileHandler(app.config['LOG_FILE'], maxBytes=5000000, backupCount=10)
    formatter = logging.Formatter('%(asctime)s | %(filename)s:%(lineno)d | %(funcName)s | %(levelname)s | %(message)s ')
    handler.setFormatter(formatter)
    handler.setLevel(app.config['LOG_LEVEL'])
    app.logger.addHandler(handler)
    app.logger.setLevel(app.config['LOG_LEVEL'])
    log = logging.getLogger('werkzeug')
    log.setLevel(app.config['LOG_LEVEL'])
    log.addHandler(handler)


def start(start_mq=True):
    spotify_helper.refresh_token_on_expired = True
    spotify_helper.return_None_on_not_found = True
    echonest_helper.return_None_on_not_found = True

    app.logger.info('Server runtime starting')
    mgh.G = cache.global_from_cache()
    if start_mq:
        app.logger.info('MQ starting')
        mq.start()


def stop():
    app.logger.info('Server runtime stopping')
    mq.stop()


if __name__ == '__main__':
    # user = UserBase.from_file('test_accounts/rudolfix-us.json')
    # import base64
    # print(base64.standard_b64encode(user.to_jsons().encode('ascii')))
    # exit(0)
    start()
    time.sleep(500)
    stop()
    print('stopped')

    # library = user_library.load_library('rudolfix-us')
    # lib_song_features, indexed_songs = mgh.load_user_library_song_features(library)
    # lib_song_features, _, __ = mgh.prepare_songs(lib_song_features, mgh.G.features_scaler)
    # top_sleepys = mgh.compute_sleep_genres(lib_song_features, library.artists)
    # top_sleepy = top_sleepys[0]
    # sleep_clusters = mgh.init_extract_genre_clusters(top_sleepy[0], mgh._dist_mod_sleep,
    #                                                                 mgh._sleepines,
    #                                                                 mgh._is_sleep_song)
    # # print('genre %s: (%s)' % (genres[genre_id], str(sleep_genre)))
    # print([(c1,c2,len(c3),c4) for c1, c2, c3, c4 in sleep_clusters])
