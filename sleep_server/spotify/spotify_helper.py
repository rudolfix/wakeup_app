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
