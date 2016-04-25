from functools import wraps
from flask import json, request

from common import spotify_helper
from api.user import User
from api import app, user_helper
from api.exceptions import *


def check_user(f):
    @wraps(f)
    def _wrap(*args, **kwargs):
        user = user_helper.check_user(request.headers.get('Authorization'))
        return f(user, *args, **kwargs)

    return _wrap


@app.route('/me/playlists')
@check_user
def get_playlists(user):
    # if playlist are not yet ready deny access
    user_helper.check_user_playlists_generation_status(user)
    # if playlist props were not set deny access
    if user.playlists is None or len(user.playlists) != 2:
        raise PlaylistsPropsNotSetException()
    # serialize json with playlist data which is a list of dictionaries
    # [{ type: 'wake_up|fall_asleep', name: , length: }, ...]
    return json.jsonify(result=user.playlists)


@app.route('/me/playlists/<playlist_type>', methods=['POST'])
@check_user
def set_playlist(user, playlist_type):
    # read playlist length from get params
    if request.values.get('desired_length') is None:
        raise PlaylistIncorrectDesiredLength(-1, int(app.config['MAXIMUM_PLAYLIST_LENGTH']))
    desired_length = int(request.values.get('desired_length'))
    # check max and min playlist length. may be 0
    if desired_length < 0 or desired_length > int(app.config['MAXIMUM_PLAYLIST_LENGTH']):
        raise PlaylistIncorrectDesiredLength(desired_length, int(app.config['MAXIMUM_PLAYLIST_LENGTH']))

    if playlist_type not in user_helper.possible_list_types:
        raise PlaylistIncorrectType(playlist_type, user_helper.possible_list_types)
    user_helper.check_user_playlists_generation_status(user)

    user_helper.save_user(user)
    user_pl_meta = user_helper.create_user_playlist(user, playlist_type, desired_length)
    return json.jsonify(result=user_pl_meta)


@app.route('/swap', methods=['POST', 'GET'])
def swap():
    auth_code = request.values.get('code')
    if app.config['TESTING']:
        token_data, status_code = spotify_helper.fake_token_for_code(app.config['TEST_REFRESH_TOKEN'])
    else:
        token_data, status_code = spotify_helper.token_for_code(auth_code, app.config['CLIENT_CALLBACK_URL'])
    if status_code == 200:
        user = user_helper.create_user(token_data)
        # init gathering info on music user has
        user_helper.gather_music_data(user)
        # refresh token will contain encrypted spotify id
        # todo: designs a better auth system with independent user id. spotify user id allows to recover user record after
        # todo: app is reinstalled or user is logged again
        token_data['refresh_token'] = User.encrypt_user_secret(user.spotify_id)
    return json.jsonify(token_data), status_code


@app.route('/refresh', methods=['POST', 'GET'])
def refresh():
    # descrypt refresh token, it will contain spotify_id (currently)
    encrypted_rf = request.values.get('refresh_token')
    spotify_id = User.decrypt_user_secret(encrypted_rf)
    # user must exist
    user = user_helper.load_user(spotify_id)
    if user.is_new:
        raise user_helper.UserDoesNotExist(request.values.get['refresh_token'])
    # follow user procedure in SWAP
    token_data, status_code = spotify_helper.refresh_token(user.spotify_refresh_token)
    if status_code == 200:
        user.update_refresh_token(token_data['access_token'], token_data['expires_in'])
        user_helper.save_user(user)
    return json.jsonify(token_data), status_code


@app.errorhandler(ApiException)
def handle_api_error(e):
    return json.jsonify(make_error_dict(e)), e.status_code

# todo: handle HTTP 500 properly, use flask blueprints to separate admin from api
# @app.errorhandler(Exception)
# def handle_error(e):
#    return json.jsonify(make_error_dict(e)), 500


def make_error_dict(e):
    return {'error': { 'status': e.status_code, 'code': e.__class__.__name__, 'message': str(e) }}
