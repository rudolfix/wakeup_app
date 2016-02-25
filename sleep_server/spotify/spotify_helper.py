from api import app
import requests
from spotipy import Spotify, SpotifyException
from functools import wraps
from api.exceptions import *
import urllib.parse


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
def get_playlist_tracks_for_user(user, spotify_id, playlist_id):
    return Spotify(auth=user.spotify_access_token).user_playlist_tracks(spotify_id, playlist_id=playlist_id,
                                                                 fields='items(added_by.id,track(uri,duration_ms))')


@spotifyapihandler
def get_or_create_playlist_by_name(user, playlist_name):
    sp_api = Spotify(auth=user.spotify_access_token)
    existing_playlists = sp_api.user_playlists(user.spotify_id, limit=50)['items']
    sleep_playlists = [pl for pl in existing_playlists if pl['name'] == playlist_name and not pl['public']]
    if len(sleep_playlists) > 0:
        return sleep_playlists[0]
    return sp_api.user_playlist_create(user.spotify_id, playlist_name, public=False)


@spotifyapihandler
def set_playlist_content(user, playlist_id, tracks):
    Spotify(auth=user.spotify_access_token).user_playlist_replace_tracks(user.spotify_id, playlist_id, tracks)


def spotify_login(redirect_url):
    params = {'client_id': app.config['CLIENT_ID'],
              'response_type': 'code',
              'redirect_uri': redirect_url,
              'scope': app.config['SPOTIFY_LOGIN_SCOPE']}
    return app.config['SPOTIFY_ACCOUNTS_ENDPOINT'] + '/authorize?' + urllib.parse.urlencode(params)


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


def fake_token_for_code(auth_code, redirect_uri):
    rf = app.config['TEST_REFRESH_TOKEN']
    token_data, status_code = refresh_token(rf)
    if status_code == 200:
        token_data['refresh_token'] = rf
    return token_data, status_code


def refresh_token(token):
    # Request a new access token using the POST:ed refresh token
    headers = {'Authorization': app.config['AUTH_HEADER']}
    form = {
        "grant_type": "refresh_token",
        "refresh_token": token
    }
    resp = requests.post(app.config['SPOTIFY_ACCOUNTS_ENDPOINT'] + '/api/token', form, headers=headers)
    return resp.json(), resp.status_code
