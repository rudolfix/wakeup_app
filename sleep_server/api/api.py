from api import app, user_helper
from api.exceptions import *
from functools import wraps
from flask import json, request


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


@app.errorhandler(ApiException)
def handle_api_error(e):
    return json.jsonify(make_error_dict(e)), e.status_code

# todo: handle HTTP 500 properly, use flask blueprints to separate admin from api
# @app.errorhandler(Exception)
# def handle_error(e):
#    return json.jsonify(make_error_dict(e)), 500


def make_error_dict(e):
    return {'error': { 'status': e.status_code, 'code': e.__class__.__name__, 'message': str(e) }}
