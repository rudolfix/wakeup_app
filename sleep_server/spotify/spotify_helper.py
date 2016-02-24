from api import app
from api.api import ApiException
import requests
from spotipy import Spotify, SpotifyException
from functools import wraps
from api.user import User


def spotifyapihandler(f):
    @wraps(f)
    def _wrap(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except SpotifyException as spoterr:
            # handle unknown tokens and expired tokens
            # todo: add logging
            # app.logger
            if spoterr.http_status == 401: # invalid or expired token
                if spoterr.code == 'Invalid access token':
                    raise SpotifyApiInvalidToken(spoterr.code, spoterr.msg)
                # todo:add automatic refresh and retry
                if spoterr.code == 'The access token expired':
                    raise SpotifyApiTokenExpired(spoterr.code, spoterr.msg)
            raise
    return _wrap


@spotifyapihandler
def get_current_user_by_token(token):
    return Spotify(auth=token).me()


@spotifyapihandler
def get_current_user(user):
    return Spotify(auth=user.spotify_access_token).me()


@spotifyapihandler
def get_playlist_for_user(user, spotify_id, playlist_id):
    return Spotify(auth=user.spotify_access_token).user_playlist(spotify_id, playlist_id=playlist_id,
                                                                 fields='items(added_by.id,track(uri,duration_ms))')


@spotifyapihandler
def get_or_create_playlist_by_name(user, playlist_name):
    sp_api = Spotify(auth=user.spotify_access_token)
    existing_playlists = sp_api.user_playlists(user.spotify_id, limit=1000)
    sleep_playlists = [pl for pl in existing_playlists if pl['name'] == playlist_name and not pl['public']]
    if len(sleep_playlists) > 0:
        return sleep_playlists[0]
    return sp_api.user_playlist_create(user.spotify_id, playlist_name, public=False)


@spotifyapihandler
def set_playlist_content(user, playlist_id, tracks):
    Spotify(auth=user.spotify_access_token).user_playlist_replace_tracks(user.spotify_id, playlist_id, tracks)


def token_for_code(auth_code, redirect_uri):
    headers = {'Authorization': app.config['AUTH_HEADER']}
    form = {'grant_type': 'authorization_code',
            'redirect_uri': redirect_uri,
            'code': auth_code}
    resp = requests.post(app.config['SPOTIFY_ACCOUNTS_ENDPOINT'] + '/api/token', form, headers=headers)
    token_data = resp.json()
    # propagate response status code
    resp.close()
    return token_data, resp.status_code


def refresh_token(token):
    # Request a new access token using the POST:ed refresh token
    headers = {'Authorization': app.config['AUTH_HEADER']}
    form = {
        "grant_type": "refresh_token",
        "refresh_token": token
    }
    resp = requests.post(app.config['SPOTIFY_ACCOUNTS_ENDPOINT'] + '/api/token', form, headers=headers)
    return resp.content, resp.status_code


class SpotifyApiInvalidToken(ApiException):
    def __init__(self, code, msg):
        super(ApiException, self).__init__('Invalid Spotify access token [%s] [%s]' % (code, msg))


class SpotifyApiTokenExpired(ApiException):
    def __init__(self, code, msg):
        super(ApiException, self).__init__('Expired Spotify access token [%s] [%s]' % (code, msg))


class SpotifyFreeUserNotSupported(ApiException):
    def __init__(self, username):
        super(ApiException, self).__init__('Free Spotify users are not supported [%s]' % username)


# class SpotifyApiCannotSwapToken(ApiException):
#     def __init__(self, code, msg):
#         super(ApiException, self).__init__('Expired Spotify access token [%s] [%s]' % (code, msg))
