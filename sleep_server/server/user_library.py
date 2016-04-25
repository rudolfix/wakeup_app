from enum import Enum
import re
import pickle
import os
from common.common import *
from common import spotify_helper
from server.exceptions import *
from server import app


class UserLibrary:
    version = 1

    def __init__(self, spotify_id):
        self.is_new = True
        self.spotify_id = spotify_id
        self.playlists = {}
        self.tracks = None
        self.unresolved_tracks = None
        self.artists = None
        self.unresolved_artists = None
        self.created_at = datetime.utcnow()
        self.updated_at = None

    @staticmethod
    def upgrade_user(user):
        pass

    @staticmethod
    def serialize(library, file):
        library._version = UserLibrary.version
        pickle.dump(library, file, protocol=4)

    @staticmethod
    def deserialize(file):
        library = pickle.load(file)
        UserLibrary.upgrade_user(library)
        if library._version != UserLibrary.version:
            raise LibraryRecordVersionMismatch(library._version, UserLibrary.version)
        library.is_new = False
        return library


class UserTrackSourceType(Enum):
    library = 1
    followed_artist = 2
    playlist = 3


ignored_playlists_re = [re.compile(r) for r in (['\*Sleep App', 'sleep.+', 'wake.+'])]


def extract_user_track(track, added_at, package_id, source):
    return {'spotify_id': track['uri'], 'song_id': None, 'package_id': package_id, 'source': source,
            'popularity': track['popularity'] or 0, 'artist_sp_ids': [artist['uri'] for artist in track['artists']],
            'artist_id': None, 'added_at': added_at, 'user_preference': 0, 'playlists': []}


def build_user_library(user, library):
    # get user library tracks
    # track attrs to store (spotify_id, song_id (when resolved), album id, source, popularity, artist_spot_id,
    # artist_id, date_added, reco_info)
    extracted_tracks = {}
    extracted_artists = {}
    library_tracks = spotify_helper.get_user_library_tracks(user)
    for item in library_tracks:
        track = item['track']
        if track['id'] not in extracted_tracks:
            extracted_tracks[track['id']] = extract_user_track(track, parse_iso8601date(item['added_at']),
                                                                track['album']['uri'], UserTrackSourceType.library)

    # get followed artists
    followed_artists = spotify_helper.get_user_followed_artists(user)
    for artist in followed_artists:
        if artist['id'] not in extracted_artists:
            extracted_artists[artist['id']] = {'spotify_id': artist['uri'], 'popularity': artist['popularity'] or 0,
                                               'followers': artist['followers']['total'], 'artist_id': None,
                                               'added_at': datetime.utcnow()}
    # scan playlists
    extracted_pl_tracks = {}
    playlists = [p for p in spotify_helper.get_playlists_for_user(user, user.spotify_id)
                 if p['owner']['id'] == user.spotify_id and not any([rx.match(p['name'])
                                                                     for rx in ignored_playlists_re])]
    for playlist in playlists:
        # check only the new or playlists with changed count (store in extracted playlists)
        pl_id = playlist['id']
        if pl_id not in library.playlists or playlist['snapshot_id'] != library.playlists[pl_id]['snapshot_id']:
            # check only 300 songs in playlits max
            pl_tracks = spotify_helper.get_playlist_tracks_for_user(user, user.spotify_id, pl_id, max_tracks=300)
            newest_added_at = datetime(2008, 1, 1)
            for item in pl_tracks:
                track = item['track']
                track_id = track['id']
                added_at = parse_iso8601date(item['added_at'])
                newest_added_at = max(newest_added_at, added_at)
                if track_id not in extracted_pl_tracks:
                    extracted_pl_tracks[track_id] = extract_user_track(track, added_at,
                                                                track['album']['uri'], UserTrackSourceType.playlist)
                else:
                    # always keep newest timestamp
                    extracted_pl_tracks[track_id]['added_at'] = max(added_at, extracted_pl_tracks[track_id]['added_at'])
                extracted_pl_tracks[track_id]['playlists'].append(pl_id)
            # save playlist props
            if pl_id not in library.playlists:
                library.playlists[pl_id] = {'uri': playlist['uri'], 'total': playlist['tracks']['total'],
                                            'last_modified': newest_added_at, 'snapshot_id': playlist['snapshot_id']}
            else:
                library.playlists[pl_id]['total'] = playlist['tracks']['total']
                library.playlists[pl_id]['last_modified'] = newest_added_at
                library.playlists[pl_id]['snapshot_id'] = playlist['snapshot_id']

    # add max 1000 newest tracks
    added_pl_tracks = 0
    for track_id, track in sorted(extracted_pl_tracks.items(), key=lambda x: x[1]['added_at'], reverse=True):
        if track_id not in extracted_tracks and added_pl_tracks < 1000:
            extracted_tracks[track_id] = track
            added_pl_tracks += 1
        else:
            extracted_tracks[track_id]['playlists'].extend(track['playlists'])
            extracted_tracks[track_id]['added_at'] = max(extracted_tracks[track_id]['added_at'], track['added_at'])
    # transfer data from resolved tracks
    if library.tracks is not None:
        for r_track_id, r_track in sorted(library.tracks.items(), key=lambda x: x[1]['added_at'], reverse=True):
            if r_track_id not in extracted_tracks:
                # this may be deleted library track or playlist track that was not modified so was not read again
                preserved_playlists = [pl_id for pl_id in r_track['playlists'] if pl_id in library.playlists]
                if len(preserved_playlists) > 0 and added_pl_tracks < 100:
                    r_track['playlists'] = preserved_playlists
                    r_track['source'] = UserTrackSourceType.playlist
                    added_pl_tracks += 1
            else:
                # preserve: added_at (newest), playlists, song_id, artist_id
                track = extracted_tracks[r_track_id]
                # preserve references to playlists that still exists and not present in 'track'
                track['playlists'].extend([pl_id for pl_id in r_track['playlists'] if pl_id in library.playlists and
                                           pl_id not in track['playlists']])
                track['added_at'] = max(track['added_at'], r_track['added_at'])
                track['song_id'] = r_track['song_id']
                track['artist_id'] = r_track['artist_id']
    # transfer data from resolved artists
    if library.artists is not None:
        for artist_id, artist in library.artists.items():
            if artist_id in extracted_artists:
                extracted_artists[artist_id]['artist_id'] = artist['artist_id']
                extracted_artists[artist_id]['added_at'] = artist['added_at']
    # get top user tracks and update stored tracks with preference store

    def update_from_top(term_type, score):
        top_tracks = spotify_helper.get_user_top_tracks(user, term_type)
        for track in top_tracks:
            if track['id'] in extracted_tracks:
                extracted_tracks[track['id']]['user_preference'] += score # 0.5 for short term
    update_from_top('short_term', 0.5)
    update_from_top('medium_term', 0.25)

    # store as unresolved
    library.unresolved_tracks = extracted_tracks
    library.uresolved_artists = extracted_artists

    return extracted_tracks, extracted_artists


def load_library(spotify_id):
    path = app.config['USER_STORAGE_URI'] + spotify_id + '.library'
    if os.path.isfile(path):
        try:
            with open(path, 'br') as f:
                library = UserLibrary.deserialize(f)
                library.is_new = False
        except (pickle.PickleError, TypeError, EOFError):
            # delete file and raise
            os.remove(path)
            raise
        return library
    else:
        library = UserLibrary(spotify_id) # return empty record
        return library


def save_user(library):
    path = app.config['USER_STORAGE_URI'] + library.spotify_id + '.library'
    with open(path, 'bw') as f:
        library.updated_at = datetime.utcnow()
        UserLibrary.serialize(library, f)
