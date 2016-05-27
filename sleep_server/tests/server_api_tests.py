from functools import wraps
import os, inspect
currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
os.sys.path.insert(0, parentdir)

from common import music_graph_client as mgc
from common.user_base import UserBase
from server import music_graph_helper as mgh, user_library as ul, server


def apitest(f):
    @wraps(f)
    def _wrap(*args, **kwargs):
        try:
            print(f)
            v = f(*args, **kwargs)
            if v is not None:
                print(v)
        except Exception as exc:
            print(str(type(exc)) + ':' + str(exc))
    return _wrap


def test_mgc_sweep(user):
    playlists = mgc.get_possible_playlists(user)
    for pt in playlists:
        l = playlists[pt]
        for d in l:
            print('creating playlist %s in %s' % (d['name'], pt))
            mgc.create_playlist(user, pt, 60*60*1000, d['plid'])


def test_mgc(user, user_unk):
    apitest(mgc.get_library)(user)
    apitest(mgc.get_library)(user_unk)
    apitest(mgc.get_possible_playlists)(user)
    apitest(mgc.get_possible_playlists)(user, 'fall_asleep')
    apitest(mgc.get_possible_playlists)(user, 'wake_up')
    apitest(mgc.create_playlist)(user, 'fall_asleep', 60*60*1000,828)


def test_get_best_playlist_id(user, playlist_type):
    server.start()
    library = ul.load_library(user.spotify_id)
    ul._delete_library(user.spotify_id, ul.UserLibraryProps)
    lib_song_features, _ = mgh.load_user_library_song_features(library)
    lib_song_features, _, _ = mgh.prepare_songs(lib_song_features, mgh.G.features_scaler)
    if playlist_type == 'fall_asleep':
        top_sleepys, _ = mgh.compute_sleep_genres(lib_song_features, library.artists)
    else:
        top_sleepys, _ = mgh.compute_wakeup_genres(lib_song_features, library.artists)

    for _ in range(10):
        playlist_id = ul.get_best_playlist_id(playlist_type, library, top_sleepys, keep_n_last=4)
        print('got plid %i' % playlist_id)

    ul._delete_library(user.spotify_id, ul.UserLibraryProps)

    for _ in range(len(top_sleepys)+5):
        playlist_id = ul.get_best_playlist_id(playlist_type, library, top_sleepys, keep_n_last=len(top_sleepys)+1)
        print('got plid %i' % playlist_id)


user = UserBase.from_file('test_accounts/rudolfix-us.json')
user_unk = UserBase.from_file('test_accounts/rudolfix-us.json')
user_unk.spotify_id = 'unk'
apitest(test_mgc_sweep)(user)
# test_get_best_playlist_id(user, 'fall_asleep')
