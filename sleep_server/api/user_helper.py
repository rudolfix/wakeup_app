import math
import os.path
import pickle
import random
import shutil
from functools import reduce
from datetime import datetime

from api import app
from api.exceptions import *
from api.user import User
from common import spotify_helper, common, music_graph_client as mgc
from common.exceptions import *


def _create_playlist_item(playlist_type, uri, actual_length, desired_length):
    return {'type': playlist_type, 'uri': uri, 'length': actual_length, 'desired_length': desired_length}


def create_user(token_data):
    # get user record from spotify
    sp_record = spotify_helper.get_current_user_by_token(token_data['access_token'])
    # bail on free users
    if sp_record['product'] != 'premium':
        raise SpotifyFreeUserNotSupported(sp_record['id'])
    # now load user by spotify id as it may already exist (we cant assume we track all tokens etc.)
    user = load_user(sp_record['id'])
    # set user name to the new/restored record & etc & save
    user.spotify_id = sp_record['id']
    user.spotify_token_expiration = token_data['expires_in']
    user.spotify_access_token = token_data['access_token']
    user.spotify_refresh_token = token_data['refresh_token']
    # add empty playlist items with default settings so they will be created when library is resolved
    if len(user.playlists) == 0:
        for pl_type in common.possible_list_types:
            user.playlists.append(_create_playlist_item(pl_type, None, None, app.config['DEFAULT_PLAYLIST_LENGTH']))
    save_user(user)

    return user


def check_user(auth_header):
    if auth_header is None or len(auth_header) == 0:
        raise SpotifyApiInvalidToken('invalid_auth_header', 'Authorization header in valid format not provided')
    # get spotify id from user secret
    secret, access_token = auth_header.split(' ')
    spotify_id = User.decrypt_user_secret(secret)
    # user must exist
    user = load_user(spotify_id)
    if user.is_new:
        raise UserDoesNotExist(secret)
    # auth token should match
    if user.spotify_access_token != access_token:
        raise spotify_helper.SpotifyApiInvalidToken('stored_user_token_mismatch',
                                                    'Access token stored with user record differs from token'
                                                    ' sent form client')
    return user


def load_user(spotify_id):
    path = app.config['USER_STORAGE_URI'] + spotify_id
    if os.path.isfile(path):
        try:
            with open(path, 'br') as f:
                user = User.deserialize(f)
                user.is_new = False
                # user = json.load(f, object_hook=User)
        except (pickle.PickleError, TypeError, EOFError):
            # delete file and raise
            os.remove(path)
            raise
        return user
    else:
        user = User(spotify_id) # return empty record
        return user


def create_user_playlist(user, playlist_type, desired_length, playlist_id=None):
    # create or update spotify playlist form list of playlists on Sarnecka's Spotify account
    # source_playlist = spotify_helper.get_playlist_tracks_for_user(user, '1130122659',
    #                                                        '1v1Do2ukgKZ64wCuOrBnug' if playlist_type == 'wake_up' else
    #                                                        '4rk4vb5hjM2jC5HFaOKRAL')
    # desired length in milliseconds
    if desired_length == 0:
        source_playlist = []
        actual_length = 0
    else:
        lib_playlist = mgc.create_playlist(user, playlist_type, desired_length, playlist_id)[playlist_type]
        source_playlist = lib_playlist['tracks']
        actual_length = lib_playlist['duration_ms']
        # remove randomly until list fits the desired time
        # pl_len = lambda pl: reduce(lambda x, y: x + y['track']['duration_ms'], pl, 0)
        # actual_length = pl_len(source_playlist)
        # while len(source_playlist) > 2:  # first and last songs are always here
        #     rem_idx = random.randrange(1, len(source_playlist) - 1)
        #     rem_item = source_playlist[rem_idx]
        #     if math.fabs(actual_length-rem_item['track']['duration_ms']-desired_length) > \
        #             math.fabs(actual_length-desired_length):
        #         break
        #     source_playlist.remove(rem_item)
        #     actual_length = pl_len(source_playlist)
    # create/update spotify playlist
    sp_user_pl = spotify_helper.get_or_create_playlist_by_name(user, common.predefined_playlists[playlist_type])
    # [item['track']['uri'] for item in source_playlist]
    spotify_helper.set_playlist_content(user, sp_user_pl['id'], source_playlist)
    # save user records
    user_pl_meta = _create_playlist_item(playlist_type, sp_user_pl['uri'], actual_length, desired_length)
    existing_user_pl_meta = [pl for pl in user.playlists if pl['type'] == playlist_type]
    if len(existing_user_pl_meta) == 1:
        user.playlists.remove(existing_user_pl_meta[0])
    user.playlists.append(user_pl_meta)
    return user_pl_meta


def gather_music_data(user):
    can_be_updated = True
    # todo: update when not resolved or when library was not updated in X days, currently we always update
    try:
        can_be_updated = mgc.get_library(user)['can_be_updated']
    except LibraryNotExistsException:
        pass
    if can_be_updated:
        mgc.resolve_library(user)


def throw_on_user_playlists_not_ready(user):
    lib_status = mgc.get_library(user)
    if not lib_status['is_resolved']:
        raise PlaylistsDataNotReadyException()
    # if not user.is_playlists_ready:
    #     # mockup playlist wait time max 2 mins, min 15 sec
    #     min_gen = app.config['MOCKUP_MIN_PLAYLIST_GEN_SEC']
    #     max_gen = app.config['MOCKUP_MAX_PLAYLIST_GEN_SEC']
    #     if (datetime.utcnow() - user.created_at).seconds < random.randrange(min_gen, max_gen):
    #         raise PlaylistsDataNotReadyException()
    #     else:
    #         user.is_playlists_ready = True
    #         save_user(user)


def save_user(user):
    assert user.spotify_id is not None and len(user.spotify_id) > 0, 'spotify_id must be present before saving user'
    assert user.spotify_access_token is not None and len(user.spotify_access_token) > 0, \
        'spotify_access_token must be present before saving user'
    assert user.spotify_refresh_token is not None and len(user.spotify_refresh_token) > 0,\
        'spotify_encrypted_refresh_token must be present before saving user'
    assert user.spotify_token_expiration is not None, 'spotify_token_expiration must be present before saving user'

    path = app.config['USER_STORAGE_URI'] + user.spotify_id
    with open(path, 'bw') as f:
        user.updated_at = datetime.utcnow()
        User.serialize(user, f)


def init_user_storage():
    path = app.config['USER_STORAGE_URI']
    shutil.rmtree(path, ignore_errors=True)
    os.mkdir(path)