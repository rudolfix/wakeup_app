import urllib.parse
from functools import wraps

import requests
from spotipy import Spotify, SpotifyException
from common.common import *
from common.user_base import UserBase
from common.config import ConfigBase
from common.exceptions import SpotifyApiObjectNotFoundException, SpotifyApiInvalidToken, SpotifyApiTokenExpired

refresh_token_on_expired = False
return_None_on_not_found = False
_config = ConfigBase()


def spotifyapihandler(f):
    @wraps(f)
    def _wrap(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except SpotifyException as spoterr:
            # handle unknown tokens and expired tokens
            if spoterr.http_status == 401: # invalid or expired token
                if 'Invalid access token' in spoterr.msg:
                    raise SpotifyApiInvalidToken(spoterr.code, spoterr.msg)
                if 'The access token expired' in spoterr.msg:
                    if refresh_token_on_expired:
                        if isinstance(args[0], UserBase):
                            user = args[0]
                            token_data, status_code = refresh_token(user.spotify_refresh_token)
                            if status_code == 200:
                                user.update_refresh_token(token_data['access_token'], token_data['expires_in'])
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
def get_playlist_tracks_for_user(user, spotify_id, playlist_id, remove_local=True, max_tracks=500):
    spotify = Spotify(auth=user.spotify_access_token)
    results = spotify.user_playlist_tracks(spotify_id, playlist_id=playlist_id,
                                fields='items(is_local,added_by.id,added_at,track(id,uri,duration_ms,artists(uri),'
                                       'album(uri),popularity)),total,next,prev')
    tracks = results['items']
    while results['next'] and len(tracks) < max_tracks:
        results = spotify.next(results)
        tracks.extend(results['items'])
    if remove_local:
        tracks = [t for t in tracks if not t['is_local']]

    return tracks


@spotifyapihandler
def get_user_followed_artists(user):
    spotify = Spotify(auth=user.spotify_access_token)
    results = spotify.current_user_followed_artists(50)['artists']
    artists = results['items']
    while results['next']:
        results = spotify.next(results)['artists']
        artists.extend(results['items'])

    return artists


@spotifyapihandler
def get_user_library_tracks(user, retrieve_until_date=None):
    def trim_if_older(r, until_date):
        if until_date is None:
            return False, r['items']  # not done
        else:
            # fortunately, spotify returns UTC time so we can use naive datetime objects
            r_filtered = [item for item in r['items'] if parse_iso8601date(item['added_at']) > until_date]
            return len(r_filtered) == len(r), r_filtered  # not done if not items removed

    spotify = Spotify(auth=user.spotify_access_token)
    results = spotify.current_user_saved_tracks(limit=50)
    done, tracks = trim_if_older(results, retrieve_until_date)
    while results['next'] and not done:
        results = spotify.next(results)
        done, more_tracks = trim_if_older(results, retrieve_until_date)
        tracks.extend(more_tracks)

    return tracks


@spotifyapihandler
def get_playlist_for_user(user, spotify_id, playlist_id):
    return Spotify(auth=user.spotify_access_token).user_playlist(spotify_id, playlist_id,
                                fields='items(!track), name, collaborative, id, owner, total, description')


@spotifyapihandler
def get_similar_artists(user, spotify_id):
    return Spotify(auth=user.spotify_access_token).artist_related_artists(spotify_id)


def get_playlists_for_user(user, spotify_id):
    sp_api = Spotify(auth=user.spotify_access_token)
    results = sp_api.user_playlists(spotify_id, limit=50)
    playlists = results['items']
    while results['next']:
        results = sp_api.next(results)
        playlists.extend(results['items'])
    return playlists


@spotifyapihandler
def get_or_create_playlist_by_name(user, playlist_name):
    sp_api = Spotify(auth=user.spotify_access_token)
    existing_playlists = get_playlists_for_user(user, user.spotify_id)
    sleep_playlists = [pl for pl in existing_playlists if pl['name'] == playlist_name and not pl['public']]
    if len(sleep_playlists) > 0:
        return sleep_playlists[0]
    return sp_api.user_playlist_create(user.spotify_id, playlist_name, public=False)


@spotifyapihandler
def set_playlist_content(user, playlist_id, tracks):
    Spotify(auth=user.spotify_access_token).user_playlist_replace_tracks(user.spotify_id, playlist_id, tracks)


@spotifyapihandler
def get_tracks(user, track_ids, market='from_token'):
    sp_api = Spotify(auth=user.spotify_access_token)
    # the order will be preserved, null will be returned for non existing tracks
    tracks = []
    for chunk in list_chunker(track_ids, 50):
        tlist = [sp_api._get_id('track', t) for t in chunk]
        t_frag = sp_api._get('tracks/?ids=%s&market=%s' % (','.join(tlist), market))
        tracks.extend(t_frag['tracks'])
    return tracks


@spotifyapihandler
def get_user_top_tracks(user, term_type):
    sp_api = Spotify(auth=user.spotify_access_token)
    # the order will be preserved, null will be returned for non existing tracks
    return sp_api._get('me/top/tracks?time_range=%s&limit=50' % term_type)['items']


def resolve_tracks_for_user(user, track_mappings):
    # track_mappings: [(song id, spotify track id),...] (where song can have many tracks)
    # this method will call spotify with a list of songs where each can have many tracks (instances)
    # as a result a normalized list is returned (1) song : track 1:1 (2) non existing tracks removed
    # (3) playable whenever possible
    # song_id must be >= 0
    track_ids, _ = zip(*track_mappings)
    spotify_tracks = get_tracks(user, track_ids)
    assert len(spotify_tracks) == len(track_ids), 'number of tracks from spotify must eq no. input tracks'
    added_songs = {}
    resolved_tracks = []
    resolved_mappings = []
    for track, mapping in zip(spotify_tracks, track_mappings):
        if track is None or not track['is_playable']:
            continue
        if mapping[1] in added_songs:  # this song was added
            continue
        added_songs[mapping[1]] = mapping[0]
        resolved_mappings.append(mapping)
        resolved_tracks.append(track)
    return resolved_tracks, added_songs, resolved_mappings


def spotify_login(redirect_url):
    params = {'client_id': _config.SPOTIFY_CLIENT_ID,
              'response_type': 'code',
              'redirect_uri': redirect_url,
              'scope': _config.SPOTIFY_LOGIN_SCOPE}
    return _config.SPOTIFY_ACCOUNTS_ENDPOINT + '/authorize?' + urllib.parse.urlencode(params)


def token_for_code(auth_code, redirect_uri):
    headers = {'Authorization': _config.AUTH_HEADER}
    form = {'grant_type': 'authorization_code',
            'redirect_uri': redirect_uri,
            'code': auth_code}
    resp = requests.post(_config.SPOTIFY_ACCOUNTS_ENDPOINT + '/api/token', form, headers=headers)
    token_data = resp.json()
    # propagate response status code
    resp.close()
    return token_data, resp.status_code


def fake_token_for_code(test_refresh_token):
    token_data, status_code = refresh_token(test_refresh_token)
    if status_code == 200:
        token_data['refresh_token'] = test_refresh_token
    return token_data, status_code


def refresh_token(token):
    # Request a new access token using the POST:ed refresh token
    headers = {'Authorization': _config.AUTH_HEADER}
    form = {
        "grant_type": "refresh_token",
        "refresh_token": token
    }
    resp = requests.post(_config.SPOTIFY_ACCOUNTS_ENDPOINT + '/api/token', form, headers=headers)
    return resp.json(), resp.status_code


def split_playlist_uri(playlist_uri):
    # split spotify:user:clement.b:playlist:5XfVVYoIR8JVCAscW0WbNM into user_id, playlist_id
    components = playlist_uri.split(':')
    return components[2], components[4]
