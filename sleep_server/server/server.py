import inspect
import os, sys, traceback
import time
import random
from threading import Thread, Lock
from flask import json, request
import pika
import base64
from functools import wraps

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
os.sys.path.insert(0, parentdir)
from common.user_base import UserBase
from common import spotify_helper
from server import app, fpika, song_helper, echonest_helper, user_library, music_graph_helper, cache
from common.exceptions import ApiException, LibraryNotExistsException, LibraryNotResolvedException
from common.common import possible_list_types
from server.exceptions import MqMalformedMessageException

_ch_user_lib_updater = 'user_lib_updater'
_ch_user_lib_resolver = 'user_lib_resolver'
_mq_lock = Lock()
_mq_channels = {_ch_user_lib_updater: None, _ch_user_lib_resolver: None}


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
    send_mq_message(_ch_user_lib_updater, body)
    return 'queued', 202  # accepted


@app.route('/library/<user_id>')
def library_get_props(user_id):
    library = user_library.load_library(user_id)
    if library.is_new:
        raise LibraryNotExistsException(user_id)
    return json.jsonify(result={'created_at': library.created_at, 'updated_at': library.updated_at,
                                'is_resolved': library.is_resolved,
                                'can_be_updated': library.unresolved_tracks is None})


@app.route('/library/<user_id>/playlists')
@app.route('/library/<user_id>/playlists/<playlist_type>')
def library_list_playlists(user_id, playlist_type=None):
    library = user_library.load_library(user_id)
    if library.is_new:
        raise LibraryNotExistsException(user_id)
    if not library.is_resolved:
        raise LibraryNotResolvedException(user_id)
    lib_song_features, _ = music_graph_helper.load_user_library_song_features(library)
    lib_song_features, _, _ = music_graph_helper.prepare_songs(lib_song_features, music_graph_helper.G.features_scaler)
    add_pl_item = lambda plid, n, card, pref: {'plid': plid, 'name': n, 'card': card, 'pref': pref}
    rv = {}
    for pt in [pt for pt in possible_list_types if playlist_type is None or playlist_type == pt]:
        if pt == 'fall_asleep':
            rv[pt] = []
            top_sleepys = music_graph_helper.compute_sleep_genres(lib_song_features, library.artists)
            for gid, prevalence, sleepiness, user_pref in top_sleepys:
                name = 'based on %s with %d%% sleepiness' % (music_graph_helper.G.genres[gid], int(sleepiness*100))
                print('%s(%i): %f%% affinity:%f pref:%f' % (name, gid, 100*prevalence, 100*sleepiness, user_pref))
                rv[pt].append(add_pl_item(gid, name, prevalence, user_pref))
        if pt == 'wake_up':
            raise NotImplementedError()
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
    lib_song_features, _ = music_graph_helper.load_user_library_song_features(library)
    lib_song_features, _, _ = music_graph_helper.prepare_songs(lib_song_features, music_graph_helper.G.features_scaler)
    pl_tracks, exact_duration = None, None
    if playlist_type == 'fall_asleep':
        if playlist_id is None:
            # when playlist name is not present create playlist where user has most preferences
            top_sleepys = music_graph_helper.compute_sleep_genres(lib_song_features, library.artists)
            playlist_id = user_library.get_best_playlist_id(playlist_type, library, top_sleepys)
        # get genre clusters from cache
        sleep_clusters = cache.get_genre_clusters('sleep', playlist_id)
        # may have many clusters, select one
        cluster = sleep_clusters[random.randint(0,len(sleep_clusters)-1)]
        # get playlist with selected length
        pl_song_features, _ = music_graph_helper.get_random_song_slice_with_length(cluster[2], desired_length, 0.3)
        # returns list of spotify ids and duration
        _, indexed_songs = song_helper.prepare_playable_tracks(user, [int(f[music_graph_helper._f_song_id_i]) for f in
                                                                       pl_song_features])
        # trim playlist to exact length
        pl_tracks, exact_duration = music_graph_helper.trim_song_slice_length(indexed_songs.items(),
                                                                              pl_song_features, desired_length)
    if playlist_type == 'wake_up':
        raise NotImplementedError()

    return json.jsonify(result={playlist_type: {'duration_ms': exact_duration, 'tracks': pl_tracks}})


@app.errorhandler(ApiException)
def handle_api_error(e):
    return json.jsonify(_make_error_dict(e, e.status_code)), e.status_code


@app.errorhandler(Exception)
def handle_error(e):
    return json.jsonify(_make_error_dict(e, 500)), 500


def _make_error_dict(e, status_code):
    return {'error': {'status': status_code, 'code': e.__class__.__name__, 'message': str(e)}}


def send_mq_message(name, body):
    channel = fpika.channel()
    try:
        # todo: handle rabbit mq errors that destroy connections (fpika.return_broken_channel)
        channel.queue_declare(queue=name, durable=True)
        channel.basic_publish(exchange='',
                              routing_key=name,
                              body=body,
                              properties=pika.BasicProperties(
                                  delivery_mode=2,  # make message persistent
                              ))
    finally:
        fpika.return_channel(channel)


def mq_callback(f):
    @wraps(f)
    def _wrap(*args, **kwargs):
        ch = args[0]
        method = args[1]
        try:
            r = f(*args, **kwargs)
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return r
        except MqMalformedMessageException as mf:
            print('queue message malformed, MESSAGE DISCARDED (%s)' % str(mf))
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except:
            traceback.print_exc(file=sys.stdout)
            ch.basic_nack(delivery_tag=method.delivery_tag)

    return _wrap


def _parse_user_library_mq_msg(body):
    try:
        body = json.loads(body)
        # must have proper version
        user = UserBase.from_jsons(body['user'])
        user_id = body['user_id']
        return user_id, user
    except Exception as e:
        raise MqMalformedMessageException(str(e))


@mq_callback
def _user_lib_resolver_callback(ch, method, properties, body):
    print('RESOLVER CONSUMER received')
    start_time = time.time()
    user_id, user = _parse_user_library_mq_msg(body)
    library = user_library.load_library(user_id)
    if library.unresolved_tracks:
        _, _, _, new_artists = user_library.resolve_user_library(library, music_graph_helper.G.genres_names)
        user_library.save_library(library)
        song_helper.infer_and_store_genres_for_artists(user, new_artists, music_graph_helper.G.genres_names)
    print('RESOLVER CONSUMER done elapsed %f' % (time.time() - start_time))


@mq_callback
def _user_lib_updater_callback(ch, method, properties, body):
    print('UPDATER CONSUMER received')
    start_time = time.time()
    user_id, user = _parse_user_library_mq_msg(body)
    library = user_library.load_library(user_id)
    user_library.build_user_library(user, library)
    user_library.save_library(library)
    send_mq_message(_ch_user_lib_resolver, body)  # forward the same body to resolve queue
    print('UPDATER CONSUMER done elapsed %f' % (time.time() - start_time))


def _run_mq_consumer(name, callback, thread):
    while True:
        channel = None
        with _mq_lock:
            _mq_channels[name] = (thread, None)
        try:
            print('queue %s starting' % name)
            channel = fpika.channel()
            channel.queue_declare(queue=name, durable=True)
            channel.basic_qos(prefetch_count=1)
            tag = channel.basic_consume(callback, queue=name)
            with _mq_lock:
                _mq_channels[name] = (thread, channel)
        except Exception as exc:
            print('cannot start queue %s [%s], will try again' % (name, repr(exc)))
            if channel:
                fpika.return_broken_channel(channel)
            time.sleep(5)
            continue
        try:
            print('queue %s is consuming' % name)
            channel.start_consuming()
            fpika.return_channel(channel)
            print('queue %s shutdown' % name)
            return
        except Exception as exc:
            with _mq_lock:
                _mq_channels[name] = (thread, None)
            print('error when consuming queue %s [%s], will try again' % (name, repr(exc)))
            time.sleep(5)


def start():
    spotify_helper.refresh_token_on_expired = True
    spotify_helper.return_None_on_not_found = True
    echonest_helper.return_None_on_not_found = True

    music_graph_helper.G = cache.global_from_cache()
    thread = Thread(target=_run_mq_consumer)
    thread.daemon = True
    thread._args = (_ch_user_lib_resolver, _user_lib_resolver_callback, thread)
    thread.start()
    thread = Thread(target=_run_mq_consumer)
    thread.daemon = True
    thread._args = (_ch_user_lib_updater, _user_lib_updater_callback, thread)
    thread.start()


def stop():
    print('stopping....')
    with _mq_lock:
        for name, value in _mq_channels.items():
            if value:
                thread, channel = value
                if channel:
                    channel.start_consuming()
                thread.join(10)  # wait 10 seconds then give up


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
    # lib_song_features, indexed_songs = music_graph_helper.load_user_library_song_features(library)
    # lib_song_features, _, __ = music_graph_helper.prepare_songs(lib_song_features, music_graph_helper.G.features_scaler)
    # top_sleepys = music_graph_helper.compute_sleep_genres(lib_song_features, library.artists)
    # top_sleepy = top_sleepys[0]
    # sleep_clusters = music_graph_helper.init_extract_genre_clusters(top_sleepy[0], music_graph_helper._dist_mod_sleep,
    #                                                                 music_graph_helper.sleepines,
    #                                                                 music_graph_helper.is_sleep_song)
    # # print('genre %s: (%s)' % (genres[genre_id], str(sleep_genre)))
    # print([(c1,c2,len(c3),c4) for c1, c2, c3, c4 in sleep_clusters])
