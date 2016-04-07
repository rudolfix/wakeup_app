import inspect
import os

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
os.sys.path.insert(0,parentdir)
from api import user_helper, db
from spotify import spotify_helper
from server import song_helper, echonest_helper


# you can get multiple tracks (track_id!) as below
# http://developer.echonest.com/api/v4/song/profile?api_key=V91CRTEB0IFMAJBMB&track_id=spotify:track:56pr4kpxdUTnwxRvO175lY&track_id=spotify:track:2gJ6GosqxgL0upIgyKQAKB&track_id=spotify:track:4wQ2cmlvdg9NqXFdGufUmU&track_id=spotify:track:5Qxj5LmOb9cXtnqUbmEQWU&format=json&bucket=audio_summary&bucket=id:spotify&bucket=tracks
# spotify:user:deerwolf1:playlist:59tM9mHndQkT12GiC5IDuy (drone)

def transfer_playlist(spotify_user_id, spotify_playlist_uri, song_group_type):
    user = user_helper.load_user(spotify_user_id)
    playlist = spotify_helper.get_playlist_for_user(user, *spotify_helper.split_playlist_uri(spotify_playlist_uri))
    print('will process song group %s(%s) of type %i' % (playlist['name'], spotify_playlist_uri, song_group_type))
    songs_group = song_helper.db_create_song_group(playlist['name'], spotify_playlist_uri,
                                                   song_group_type, overwrite=True)
    tracks = spotify_helper.get_playlist_tracks_for_user(user, *spotify_helper.split_playlist_uri(spotify_playlist_uri))
    found_songs, not_found_songs = song_helper.transfer_songs_from_spotify([track['track']['uri'] for track in tracks])
    song_helper.db_update_songs_group(songs_group.GroupId,
                                      [db_s.SongId for db_s in list(found_songs)],
                                      overwrite=True)
    db.session.commit()


sleep_playlists = ['spotify:user:deerwolf1:playlist:59tM9mHndQkT12GiC5IDuy',
                   'spotify:user:clement.b:playlist:5XfVVYoIR8JVCAscW0WbNM',
                   'spotify:user:1218533624:playlist:68ZrgGtwgokdaSDFRMkm3p',
                   'spotify:user:1129402501:playlist:2rRaMerKbRuVUZWiceVVnG',
                   'spotify:user:topsify:playlist:62n7TtrAWY1BeNg54yigFe',
                   'spotify:user:redbrainylol:playlist:7Gcma8QMnpUe0sFqIti4Ey',
                   'spotify:user:1223617919:playlist:420ztXkaIEGQiWLOY0HDnp',
                   'spotify:user:mr_sluggo:playlist:0rM7fjFeBLnnCOqeeRAqQU',
                   'spotify:user:katiemae.1098:playlist:4dMDeXK2lhLiDbMR7jX7PT',
                   'spotify:user:spotify:playlist:4p0nBmAdppia9ydlTwXFCY',
                   'spotify:user:digster.se:playlist:2QUxseTrOVRHfY7hEvTNzX',
                   'spotify:user:spotify:playlist:6uNYVqbmHHVhqe7YUgV99f',
                   'spotify:user:filtr:playlist:6k6C04ObdWs3RjsabtRUQa',
                   'spotify:user:spotify_uk_:playlist:0dAcprPD1gAxffqCCtxkct',
                   'spotify:user:pippajuliesse:playlist:6kBfCO4qrApYxFfmCddDRp',
                   'spotify:user:noeieng:playlist:1WAkpBSw9BBsQgsGebfV61',
                   'spotify:user:mmages:playlist:63BvTlM88kbRzwpHpPdkdz',
                   'spotify:user:briifisher:playlist:19rkXnGQn8FO4UbwyuzMO6',
                   'spotify:user:d4tacenter:playlist:0E7fpwoRODPV6n03CYgeL7',
                   'spotify:user:loulabel_:playlist:0berFuJr7pKCChtsjby5uf',
                   'spotify:user:iines99:playlist:4ekmgGroxNSA3xvk2cGZjk']

wakeup_playlists = ['spotify:user:1199472521:playlist:6IzJjJaPk75CllWXdVdgkf',
                    'spotify:user:wakeupchile:playlist:24xA6Eqt2lLgkWpmZfGkgz',
                    'spotify:user:lynnjiao99:playlist:4WyGCvvxBFgbjclzhxIwAg',
                    'spotify:user:kika.awesome:playlist:0CseV6jJBb0Wfg1ORad8Uk',
                    'spotify:user:1147640097:playlist:4aO3ZWGSzstX5gjFG0A9p4',
                    'spotify:user:jklipana:playlist:37E8x1fhOixr96EcbpqRNS',
                    'spotify:user:valeria.tarrillo:playlist:55ktQ6lknerucwQnB8jToq',
                    'spotify:user:12159454653:playlist:0mBxAQql6FsbqSI45sMfM2',
                    'spotify:user:22tdp45w4o3nhm6v2svmvtlnq:playlist:2hThhgnD3i4xhyJokL4Q95',
                    'spotify:user:1281571048:playlist:25vWzrNAQuG4lQtQYdDk3S',
                    'spotify:user:nathyfm:playlist:2jDv8b63JOIxmKi5uNNhft',
                    'spotify:user:1188752470:playlist:1ho4XIP6mkF6V8YTUiPFG2',
                    'spotify:user:holbergra:playlist:4XkbldAjn70DY8PnCEQ4zS',
                    'spotify:user:12133327740:playlist:6qNc20afZI9eXObsDnxQNC',
                    'spotify:user:madli007:playlist:2Q7SGhfO7l4E9O0t5y7ETj']

if __name__ == '__main__':
    # set api client helpers to server mode
    spotify_helper.refresh_token_on_expired = True
    spotify_helper.return_None_on_not_found = True
    echonest_helper.return_None_on_not_found = True
    # import sleep playlists
    for plid in sleep_playlists:
        transfer_playlist('rudolfix-us', plid, 1)
    for plid in wakeup_playlists:
        transfer_playlist('rudolfix-us', plid, 2)
    # transfer_playlist('rudolfix-us', 'spotify:user:clement.b:playlist:5XfVVYoIR8JVCAscW0WbNM', 1)
    # en = song_helper.make_pyen()
    # artist = song_helper.echonest_get_artist(en, 'ARH6W4X1187B99275F')
    # artist = song_helper.echonest_get_artist(en, 'ARH6W4X1187B99274F')
    # print(artist)