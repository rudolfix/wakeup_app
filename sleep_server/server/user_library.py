from enum import Enum
import re
import pickle
import os
from functools import reduce
from random import random
from bisect import bisect
from itertools import accumulate

from common.common import *
from common import spotify_helper
from server.exceptions import *
from server import app, song_helper


class UserLibrary:
    version = 1
    storage_extension = '.library'

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

    @property
    def is_resolved(self):
        return self.tracks is not None

    @staticmethod
    def upgrade_record(user):
        pass

    @staticmethod
    def serialize(library, file):
        library._version = UserLibrary.version
        pickle.dump(library, file, protocol=4)

    @staticmethod
    def deserialize(file):
        library = pickle.load(file)
        UserLibrary.upgrade_record(library)
        if library._version != UserLibrary.version:
            raise LibraryRecordVersionMismatchException(library._version, UserLibrary.version)
        library.is_new = False
        return library


class UserLibraryProps:
    version = 1
    storage_extension = '.library_props'

    def __init__(self, spotify_id):
        self.is_new = True
        self.spotify_id = spotify_id
        self.selected_playlists = {}
        self.created_at = datetime.utcnow()
        self.updated_at = None
        # fill playlist types
        for pt in possible_list_types:
            self.selected_playlists[pt] = []

    @staticmethod
    def upgrade_record(user):
        pass

    @staticmethod
    def serialize(library, file):
        library._version = UserLibraryProps.version
        pickle.dump(library, file, protocol=4)

    @staticmethod
    def deserialize(file):
        library = pickle.load(file)
        UserLibraryProps.upgrade_record(library)
        if library._version != UserLibraryProps.version:
            raise LibraryRecordVersionMismatchException(library._version, UserLibraryProps.version)
        library.is_new = False
        return library


class UserTrackSourceType(Enum):
    library = 1
    followed_artist = 2
    playlist = 3


max_playlist_tracks = 1000
_ignored_playlists_re = [re.compile(r) for r in (['\*Sleep App', 'sleep.+', 'wake.+'])]


def _extract_user_track(track, added_at, package_id, source):
    return {'spotify_id': track['uri'], 'song_id': None, 'package_id': package_id, 'source': source,
            'popularity': track['popularity'] or 0, 'artist_sp_ids': [artist['uri'] for artist in track['artists']],
            'artist_id': None, 'added_at': added_at, 'user_preference': 0, 'playlists': []}


def _delete_library(spotify_id, lib_class):
    path = app.config['USER_STORAGE_URI'] + spotify_id + lib_class.storage_extension
    if os.path.isfile(path):
        os.remove(path)

def _load_library(spotify_id, lib_class):
    path = app.config['USER_STORAGE_URI'] + spotify_id + lib_class.storage_extension
    if os.path.isfile(path):
        try:
            with open(path, 'br') as f:
                library = lib_class.deserialize(f)
                library.is_new = False
        except (pickle.PickleError, TypeError, EOFError):
            # delete file and raise
            os.remove(path)
            raise
        return library
    else:
        library = lib_class(spotify_id) # return empty record
        return library


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
            extracted_tracks[track['id']] = _extract_user_track(track, parse_iso8601date(item['added_at']),
                                                                track['album']['uri'], UserTrackSourceType.library.value)

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
                                                                     for rx in _ignored_playlists_re])]
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
                    extracted_pl_tracks[track_id] = _extract_user_track(track, added_at,
                                                                        track['album']['uri'], UserTrackSourceType.playlist.value)
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

    # add max max_playlist_tracks newest tracks
    added_pl_tracks = 0
    for track_id, track in sorted(extracted_pl_tracks.items(), key=lambda x: x[1]['added_at'], reverse=True):
        if track_id not in extracted_tracks:
            if added_pl_tracks < max_playlist_tracks:
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
                if len(preserved_playlists) > 0 and added_pl_tracks < max_playlist_tracks:
                    extracted_tracks[r_track_id] = r_track
                    r_track['playlists'] = preserved_playlists
                    r_track['source'] = UserTrackSourceType.playlist.value
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
            # todo: add tracks from artists you follow
            # todo: add tracks when library is very small
            if track['id'] in extracted_tracks:
                extracted_tracks[track['id']]['user_preference'] += score # 0.5 for short term
    update_from_top('short_term', 0.5)
    update_from_top('medium_term', 0.25)

    # store as unresolved
    library.unresolved_tracks = extracted_tracks
    library.unresolved_artists = extracted_artists

    return extracted_tracks, extracted_artists


def resolve_user_library(library, genres_name):
    # resolve tracks without song_id (we not were able to import them from previously solved)
    tracks_no_song_id = [t for t in library.unresolved_tracks.values() if t['song_id'] is None]
    track_mappings = [(t['spotify_id'], t['artist_sp_ids'][0]) for t in tracks_no_song_id]
    songs, found_songs, not_found_songs, new_artists = song_helper.transfer_songs_with_retry(
        track_mappings,
        genres_name,
        song_type=0)
    # index songs
    indexed_songs = {}
    for song in songs:
        indexed_songs[song.SongId] = song
    # resolve tracks
    for track in tracks_no_song_id:
        if track['spotify_id'] in found_songs:
            song_id = found_songs[track['spotify_id']]
            track['song_id'] = song_id
            track['artist_id'] = indexed_songs[song_id].ArtistId
    library.tracks = library.unresolved_tracks
    library.unresolved_tracks = None
    # resolve artists
    artists_no_artist_id = [a for a in library.unresolved_artists.values() if a['artist_id'] is None]
    for artist in artists_no_artist_id:
        db_a, is_new = song_helper.transfer_artist(artist['spotify_id'], genres_name)
        if db_a is not None:
            artist['artist_id'] = db_a.ArtistId
            if is_new:
                new_artists.append(db_a)
    library.artists = library.unresolved_artists
    library.unresolved_artists = None

    return indexed_songs, found_songs, not_found_songs, new_artists


def get_best_playlist_id(playlist_type, library, possible_clusters, keep_n_last = 5):
    # get N best possible clusters that are were not yet used, ps format
    # (pl_id, prevalence, genres_affinity[i], genres_pref[i])
    library_props = load_library_props(library.spotify_id)
    sel_pl = library_props.selected_playlists[playlist_type]
    possible_pl = [pl[0] for pl in possible_clusters]
    non_sel_pl = [pl for pl in possible_clusters if pl[0] not in sel_pl]
    if len(non_sel_pl) == 0:
        # get first cluster from sel_list (oldest)
        f_plid = get_first(sel_pl, lambda plid: plid in possible_pl)
        non_sel_pl = [get_first(possible_clusters, lambda pl: pl[0] == f_plid)]
    # create cumulative weights for possible pl
    tot_w = reduce(lambda x,y: x + y[3], non_sel_pl, 0)
    non_sel_pl_cumul = list(accumulate([pl[3]/tot_w for pl in non_sel_pl]))
    # non_sel_pl_cumul.append(1.00001)
    mass = random()
    pl_idx = bisect(non_sel_pl_cumul, mass)
    if pl_idx > len(non_sel_pl_cumul):
        pl_idx = len(non_sel_pl_cumul) - 1  # for the rare(impossible case we've got mass == 1)
    print('for mass %f in %s got %i' % (mass, non_sel_pl_cumul, pl_idx))
    # add to props, save
    sel_pl_id = non_sel_pl[pl_idx][0]
    sel_pl.append(sel_pl_id)
    if len(sel_pl) > keep_n_last:
        library_props.selected_playlists[playlist_type] = sel_pl[-keep_n_last:]
    save_library(library_props)
    return sel_pl_id


def load_library(spotify_id):
    return _load_library(spotify_id, UserLibrary)


def load_library_props(spotify_id):
    return _load_library(spotify_id, UserLibraryProps)


def save_library(library):
    path = app.config['USER_STORAGE_URI'] + library.spotify_id + library.storage_extension
    with open(path, 'bw') as f:
        library.updated_at = datetime.utcnow()
        library.serialize(library, f)
