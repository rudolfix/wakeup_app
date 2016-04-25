import datetime
import inspect
import os
from ordered_set import OrderedSet

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
os.sys.path.insert(0, parentdir)
from common import spotify_helper
from common.user_base import UserBase
from server import db, song_helper, echonest_helper, user_library


# you can get multiple tracks (track_id!) as below
# http://developer.echonest.com/api/v4/song/profile?api_key=V91CRTEB0IFMAJBMB&track_id=spotify:track:56pr4kpxdUTnwxRvO175lY&track_id=spotify:track:2gJ6GosqxgL0upIgyKQAKB&track_id=spotify:track:4wQ2cmlvdg9NqXFdGufUmU&track_id=spotify:track:5Qxj5LmOb9cXtnqUbmEQWU&format=json&bucket=audio_summary&bucket=id:spotify&bucket=tracks
# spotify:user:deerwolf1:playlist:59tM9mHndQkT12GiC5IDuy (drone)


def extract_uniq_track_artist_mappings(tracks):
    track_mappings = OrderedSet()
    for track in tracks:
        artists = track['track']['artists']
        # assert len(artists) == 1, 'we cannot transfer spotify tracks that have many artists'
        track_mappings.add((track['track']['uri'], artists[0]['uri']))
    return track_mappings


def transfer_playlist(spotify_user_id, spotify_playlist_uri, song_group_type, genres_name):
    user = user_helper.load_user(spotify_user_id)
    playlist = spotify_helper.get_playlist_for_user(user, *spotify_helper.split_playlist_uri(spotify_playlist_uri))
    print('will process song group %s(%s) of type %i' % (playlist['name'], spotify_playlist_uri, song_group_type))
    songs_group = song_helper.db_create_song_group(playlist['name'], spotify_playlist_uri,
                                                   song_group_type, overwrite=True)
    tracks = spotify_helper.get_playlist_tracks_for_user(user, *spotify_helper.split_playlist_uri(spotify_playlist_uri))
    track_mappings = extract_uniq_track_artist_mappings(tracks)
    found_songs, not_found_songs, _ = song_helper.transfer_songs_with_retry(track_mappings, genres_name,
                                                                            song_type=0)
    song_helper.db_update_songs_group(songs_group.GroupId,
                                      OrderedSet([db_s.SongId for db_s in list(found_songs)]),
                                      overwrite=True)
    db.session.commit()


def transfer_user_spotify_tracks(user, genres_name):
    user = user_helper.load_user(spotify_user_id)
    tracks = spotify_helper.get_user_library_tracks(user, datetime.datetime(2008, 1, 1))
    songs_group = song_helper.db_create_song_group(spotify_user_id + ':library', spotify_user_id+':library',
                                                   3, overwrite=True)
    track_mappings = extract_uniq_track_artist_mappings(tracks)
    found_songs, not_found_songs, _ = song_helper.transfer_songs_with_retry(track_mappings, genres_name,
                                                                            song_type=0)
    song_helper.db_update_songs_group(songs_group.GroupId,
                                      OrderedSet([db_s.SongId for db_s in list(found_songs)]),
                                      overwrite=True)
    db.session.commit()


def resolve_user_library(user, genres_name):
    library = user_library.load_library(user.spotify_id)
    user_library.build_user_library(user, library)
    track_mappings = [(t['uri', t['artists'][0]]) for t in library.unresolved_tracks.values()]
    songs, found_songs, not_found_songs, new_artists = song_helper.transfer_songs_with_retry(
        track_mappings,
        genres_name,
        song_type=0)
    # index songs
    indexed_songs = {}
    for song in songs:
        indexed_songs[song.SongId] = song
    # resolve tracks
    for track in library.unresolved_tracks:
        if track['uri'] in found_songs:
            song_id = found_songs[track['uri']]
            track['song_id'] = song_id
            track['artist_id'] = indexed_songs[song_id].ArtistId
    library.tracks = library.unresolved_tracks
    library.unresolved_tracks = None
    # resolve artists
    for artist in library.unresolved_artists:
        db_a, is_new = song_helper.transfer_artist(artist['uri'], genres_name)
        if db_a is not None:
            artist['artist_id'] = db_a.ArtistId
            if is_new:
                new_artists.append(db_a)
    library.artists = library.unresolved_artists
    library.unresolved_artists = None
    # get similar artists
    for db_a in new_artists:
        similar_ids = song_helper.transfer_similar_artists(user, db_a, genres_name)
        # infer genres
        if similar_ids:
            artists_genres = song_helper.db_get_genres_for_artists(similar_ids)
            song_helper.infer_and_store_genres_for_artist(db_a.ArtistId, similar_ids, artists_genres)
    user_library.save_user(library)


def test_resolve_tracks_for_user(spotify_user_id, song_tuples):
    user = user_helper.load_user(spotify_user_id)
    tracks, added_songs = spotify_helper.resolve_tracks_for_user(user, song_tuples)


if __name__ == '__main__':
    # set api client helpers to server mode
    spotify_helper.refresh_token_on_expired = True
    spotify_helper.return_None_on_not_found = True
    echonest_helper.return_None_on_not_found = True
    _, genres_name = song_helper.db_get_genres()
    user = UserBase.from_file('test_accounts/rudolfix-us.json')
    resolve_user_library(user)
    # test_resolve_tracks_for_user('rudolfix-us', test_resolve_tracks)
    # transfer_user_library('1130122659', genres_name)
    # transfer_user_library('rudolfix-us', genres_name)
    # import sleep playlists
    # for plid in sleep_playlists_clean:
    #    transfer_playlist('rudolfix-us', plid, 1, genres_name)
    # for plid in wakeup_playlists:
    #    transfer_playlist('rudolfix-us', plid, 2)
    # transfer_playlist('rudolfix-us', 'spotify:user:clement.b:playlist:5XfVVYoIR8JVCAscW0WbNM', 1)
    # en = song_helper.make_pyen()
    # artist = song_helper.echonest_get_artist(en, 'ARH6W4X1187B99275F')
    # artist = song_helper.echonest_get_artist(en, 'ARH6W4X1187B99274F')
    # print(artist)
