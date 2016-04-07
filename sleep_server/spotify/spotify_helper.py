from api import app
import requests
from spotipy import Spotify, SpotifyException
from functools import wraps
from api.exceptions import *
from api.user import User
import urllib.parse


refresh_token_on_expired = False
return_None_on_not_found = False


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
                if 'Invalid access token' in  spoterr.msg:
                    raise SpotifyApiInvalidToken(spoterr.code, spoterr.msg)
                if 'The access token expired' in spoterr.msg:
                    if refresh_token_on_expired:
                        if isinstance(args[0], User):
                            user = args[0]
                            token_data, status_code = refresh_token(user.spotify_refresh_token)
                            if status_code == 200:
                                from api import user_helper
                                user_helper.update_refresh_token(user, token_data['access_token'],
                                                                 token_data['expires_in'])
                                return _wrap(*args, **kwargs)  # try again
                    raise SpotifyApiTokenExpired(spoterr.code, spoterr.msg)
            if spoterr.http_status == 404: # requested object not present
                if return_None_on_not_found:
                    return None
                else:
                    raise SpotifyApiObjectNotFoundException(spoterr.code, spoterr.msg)
            raise
    return _wrap


@spotifyapihandler
def get_current_user_by_token(token):
    return Spotify(auth=token).me()


@spotifyapihandler
def get_current_user(user):
    return Spotify(auth=user.spotify_access_token).me()


@spotifyapihandler
def get_playlist_tracks_for_user(user, spotify_id, playlist_id, remove_local=True):
    spotify = Spotify(auth=user.spotify_access_token)
    results = spotify.user_playlist_tracks(spotify_id, playlist_id=playlist_id,
                                fields='items(is_local,added_by.id,added_at,track(uri,duration_ms)),total,next,prev')
    tracks = results['items']
    while results['next']:
        results = spotify.next(results)
        tracks.extend(results['items'])
    if remove_local:
        tracks = [t for t in tracks if not t['is_local']]

    return tracks


@spotifyapihandler
def get_playlist_for_user(user, spotify_id, playlist_id):
    return Spotify(auth=user.spotify_access_token).user_playlist(spotify_id, playlist_id,
                                fields='items(!track), name, collaborative, id, owner, total, description')


@spotifyapihandler
def get_similar_artists(user, spotify_id):
    return Spotify(auth=user.spotify_access_token).artist_related_artists(spotify_id)


@spotifyapihandler
def get_or_create_playlist_by_name(user, playlist_name):
    sp_api = Spotify(auth=user.spotify_access_token)
    # todo: get all playlist here, not top 50. change before production!
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


def split_playlist_uri(playlist_uri):
    # split spotify:user:clement.b:playlist:5XfVVYoIR8JVCAscW0WbNM into user_id, playlist_id
    components = playlist_uri.split(':')
    return components[2], components[4]