from slumber import API, exceptions as slumberexc
from requests import exceptions as reqexc
from flask import json
import base64
from functools import wraps
from requests.auth import AuthBase

# from common.user_base import UserBase
from common.config import ConfigBase
from common.exceptions import *
from common import common as c

_config = ConfigBase()


def slumberhandler(f):
    @wraps(f)
    def _wrap(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except slumberexc.SlumberHttpBaseException as httpexc:
            user = args[0]
            resp_code = httpexc.response.status_code
            if resp_code == 404:
                raise LibraryNotExistsException(user.spotify_id)
            if resp_code == 428:
                raise LibraryNotResolvedException(user.spotify_id)
            error = json.loads(httpexc.content)['error']
            raise MusicGraphServerException(error['code'] + ':' + error['message'])
        except reqexc.ConnectionError as connerr:
            raise MusicGraphNetworkException(str(connerr))
    return _wrap


class MgsAuth(AuthBase):
    def __init__(self, auth_blob):
        self.auth_blob = auth_blob

    def __call__(self, r):
        r.headers['Authorization'] = self.auth_blob
        return r


def _get_auth(user):
    return MgsAuth(str(base64.standard_b64encode(user.to_jsons().encode('ascii')), 'ascii'))


@slumberhandler
def get_library(user):
    r = API(_config.MUSIC_GRAPH_SERVER_ENDPOINT, append_slash=False).library(user.spotify_id)
    lib_status = r.get()['result']
    lib_status['created_at'] = c.parse_iso8601datemili(lib_status['created_at'])
    if lib_status['updated_at'] is not None:
        lib_status['updated_at'] = c.parse_iso8601datemili(lib_status['updated_at'])
    return lib_status


@slumberhandler
def resolve_library(user):
    r = API(_config.MUSIC_GRAPH_SERVER_ENDPOINT, append_slash=False, auth=_get_auth(user)).library(user.spotify_id)
    return r.post()


@slumberhandler
def get_possible_playlists(user, playlist_type=None):
    r = API(_config.MUSIC_GRAPH_SERVER_ENDPOINT, append_slash=False).library(user.spotify_id).playlists(playlist_type)
    return r.get()['result']


@slumberhandler
def create_playlist(user, playlist_type, desired_length, playlist_id=None):
    # slumber does not unpack tuples so multiple params do not work so
    if playlist_id is not None:
        playlist_type += '/' + str(playlist_id)
    r = API(_config.MUSIC_GRAPH_SERVER_ENDPOINT, append_slash=False, auth=_get_auth(user))\
        .library(user.spotify_id)\
        .playlists(playlist_type)
    return r.post(desired_length=desired_length)['result']
