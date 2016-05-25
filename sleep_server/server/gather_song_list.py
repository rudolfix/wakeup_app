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


def transfer_playlist(user, spotify_playlist_uri, song_group_type, genres_name):
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
    tracks = spotify_helper.get_user_library_tracks(user, datetime.datetime(2008, 1, 1))
    songs_group = song_helper.db_create_song_group(user.spotify_id + ':library', user.spotify_id+':library',
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
    _, _, _, new_artists = user_library.resolve_user_library(library, genres_name)
    song_helper.infer_and_store_genres_for_artists(user, new_artists, genres_name)
    user_library.save_library(library)


def test_resolve_tracks_for_user(user, song_tuples):
    tracks, added_songs, _ = spotify_helper.resolve_tracks_for_user(user, song_tuples)


if __name__ == '__main__':
    # set api client helpers to server mode
    spotify_helper.refresh_token_on_expired = True
    spotify_helper.return_None_on_not_found = True
    echonest_helper.return_None_on_not_found = True
    _, genres_name = song_helper.db_get_genres()
    # rudolfix-us
    user = UserBase.from_file('test_accounts/1130122659.json')
    resolve_user_library(user, genres_name)
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
