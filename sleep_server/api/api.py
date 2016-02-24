from api import app, user_helper
from functools import wraps, reduce
from spotify import spotify_helper
from datetime import datetime, timezone
import random
from flask import json, request
import math


def check_user(f):
    @wraps(f)
    def _wrap(*args, **kwargs):
        user = user_helper.check_user(request.headers.get('Authorization'))
        return f(user, *args, **kwargs)

    return _wrap


@app.route('/me/playlists')
@check_user
def get_playlists(user):
    # mockup playlist wait time max 2 mins, min 15 sec
    if (datetime.now(timezone.utc) - user.created_at).seconds + 15 < random.randrange(15, 2*60):
        raise PlaylistsDataNotReadyException()
    # if playlist props were not set deny access
    if user.playlists is None or len(user.playlists) != 2:
        raise PlaylistsPropsNotSetException()
    # serialize json with playlist data which is a list of dictionaries
    # [{ type: 'wake_up|fall_asleep', name: , length: }, ...]
    return json.jsonify(user.playlists)


@app.route('/me/playlists/<playlist_type>', methods=['POST'])
@check_user
def set_playlist(user, playlist_type):
    # read playlist length from get params
    desired_length = int(request.args.get('desired_length'))
    # check max and min playlist length. may be 0
    if desired_length < 0 or desired_length > int(app.config['MAXIMUM_PLAYLIST_LENGTH']):
        raise PlaylistIncorrectDesiredLength(desired_length, int(app.config['MAXIMUM_PLAYLIST_LENGTH']))
    possible_list_types = ['wake_up', 'fall_asleep']
    if playlist_type not in possible_list_types:
        raise PlaylistIncorrectType(playlist_type, possible_list_types)
    # mockup playlist wait time max 2 mins, min 15 sec
    if (datetime.now(timezone.utc) - user.created_at).seconds + 15 < random.randrange(15, 2*60):
        raise PlaylistsDataNotReadyException()
    # create or update spotify playlist form list of playlists on Sarnecka's Spotify account
    source_playlist = spotify_helper.get_playlist_for_user(user, '1130122659',
                                                           '1v1Do2ukgKZ64wCuOrBnug' if playlist_type == 'wake_up' else
                                                           '4rk4vb5hjM2jC5HFaOKRAL')['items']
    if desired_length == 0:
        source_playlist = []
        actual_length = 0
    else:
        # remove randomly until list fits the desired time
        pl_len = lambda pl: reduce(lambda x, y: int(x['duration_ms']) + int(y['duration_ms']), pl)
        actual_length = pl_len(source_playlist)
        while len(source_playlist) - 2 > 2: # first and last songs are always here
            rem_idx = random.randrange(1, len(source_playlist) - 2)
            rem_item = source_playlist[rem_idx]
            if math.fabs(actual_length-int(rem_item['track']['duration_ms'])) > actual_length:
                break
            actual_length = pl_len(source_playlist)
    # create/update spotify playlist
    sp_user_pl = spotify_helper.get_or_create_playlist_by_name(user,
                                                               '*Sleep App - Wake Up*' if playlist_type == 'wake_up' else
                                                               '*Sleep App - Fall Asleep*')
    spotify_helper.set_playlist_content(user, sp_user_pl, [item['uri'] for item in source_playlist])
    # save user records
    user_pl_meta = {'type': playlist_type, 'uri': sp_user_pl['uri'], 'length': actual_length}
    existing_user_pl_meta = [pl for pl in user.playlists if pl.type == playlist_type]
    if len(existing_user_pl_meta) == 1:
        user.playlists.remove(existing_user_pl_meta[0])
    user.playlists.append(user_pl_meta)
    user_helper.save_user(user)

    return json.jsonify(user_pl_meta)


@app.route('/')
def hello_world():
    return str.format('Hello World {0} {1}', __name__, app.config['AUTH_HEADER'])

# todo: handle API exceptions properly
# check the authorization token, if user not exists return 401 Access Denied -> must re-login
# if free user or token seems expired, re-check at spotify, return Forbidden for free user
# if user music is still being processes return HTTP 428
# if playlist properties were not set return 204 empty response


class ApiException(Exception):
    pass


class PlaylistsDataNotReadyException(ApiException):
    def __init__(self):
        super(ApiException, self).__init__('Playlists data still not processed')


class PlaylistIncorrectDesiredLength(ApiException):
    def __init__(self, actual_length, max_length):
        super(ApiException, self).__init__('Playlists length can be from 0 to %i, actual value is %i' %
                                           (max_length, actual_length))


class PlaylistIncorrectType(ApiException):
    def __init__(self, actual_type, possible_types):
        super(ApiException, self).__init__('Incorrect playlist type, possible values %s, actual value %s' %
                                           (actual_type, possible_types))


class PlaylistsPropsNotSetException(ApiException):
    def __init__(self):
        super(ApiException, self).__init__('You should set playlist properties before obtaining them')
