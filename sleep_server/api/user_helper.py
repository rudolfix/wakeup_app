from api import app
import os.path, shutil
import pickle
from datetime import datetime, timezone
from api.user import User
from api.exceptions import *
from spotify import spotify_helper
import random


def create_user(token_data):
    # get user record from spotify
    sp_record = spotify_helper.get_current_user_by_token(token_data['access_token'])
    # bail on free users
    if sp_record['product'] != 'premium':
        raise spotify_helper.SpotifyFreeUserNotSupported(sp_record['id'])
    # now load user by spotify id as it may already exist (we cant assume we track all tokens etc.)
    user = load_user(sp_record['id'])
    # set user name to the new/restored record & etc & save
    user.spotify_id = sp_record['id']
    user.spotify_token_expiration = token_data['expires_in']
    user.spotify_access_token = token_data['access_token']
    user.spotify_refresh_token = token_data['refresh_token']
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


def check_user_playlists_generation_status(user):
    if not user.is_playlists_ready:
        # mockup playlist wait time max 2 mins, min 15 sec
        min_gen = app.config['MOCKUP_MIN_PLAYLIST_GEN_SEC']
        max_gen = app.config['MOCKUP_MAX_PLAYLIST_GEN_SEC']
        if (datetime.now(timezone.utc) - user.created_at).seconds < random.randrange(min_gen, max_gen):
            raise PlaylistsDataNotReadyException()
        else:
            user.is_playlists_ready = True
            save_user(user)


def save_user(user):
    assert user.spotify_id is not None and len(user.spotify_id) > 0, 'spotify_id must be present before saving user'
    assert user.spotify_access_token is not None and len(user.spotify_access_token) > 0, \
        'spotify_access_token must be present before saving user'
    assert user.spotify_refresh_token is not None and len(user.spotify_refresh_token) > 0,\
        'spotify_encrypted_refresh_token must be present before saving user'
    assert user.spotify_token_expiration is not None, 'spotify_token_expiration must be present before saving user'

    path = app.config['USER_STORAGE_URI'] + user.spotify_id
    with open(path, 'bw') as f:
        user.updated_at = datetime.now(timezone.utc)
        User.serialize(user, f)


def init_user_storage():
    path = app.config['USER_STORAGE_URI']
    shutil.rmtree(path, ignore_errors=True)
    os.mkdir(path)