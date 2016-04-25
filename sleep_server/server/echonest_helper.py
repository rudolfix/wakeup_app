import pyen
import inspect
import os
from functools import wraps
import queue

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
os.sys.path.insert(0,parentdir)
from server import app
from server.exceptions import *


return_None_on_not_found = False
_key_queue = queue.Queue()
for api_key in app.config['ECHONEST_API_KEYS']:
    _key_queue.put(api_key)


def echonestnonehandler(f):
    @wraps(f)
    def _wrap(*args, **kwargs):
        api_key = _key_queue.get()
        try:
            return f(_make_pyen(api_key), *args, **kwargs)
        except pyen.PyenException as pyen_exc:
            # code == 5 -> invalid parameter but also means not found
            if pyen_exc.code == 5:
                if return_None_on_not_found:
                    return None
                else:
                    raise EchonestApiObjectNotFoundException(pyen_exc.code, pyen_exc.msg)
            raise
        finally:
            _key_queue.put(api_key)
    return _wrap


@echonestnonehandler
def get_artist(pyen, any_id):
    return pyen.get('artist/profile', id=any_id, bucket=['hotttnesss','id:spotify', 'genre'])['artist']


@echonestnonehandler
def get_artists_in_genre(pyen, genre_name, check_top_artists):
    return pyen.get('genre/artists', results=check_top_artists, name=genre_name, bucket=['hotttnesss',
                                                                                                 'id:spotify', 'genre'])


@echonestnonehandler
def get_top_songs_for_artist(pyen, artist_id, check_top_artist_songs):
    return pyen.get('song/search', results=check_top_artist_songs, artist_id=artist_id,
                            bucket=['song_hotttnesss', 'id:spotify', 'audio_summary', 'tracks'],
                            sort='song_hotttnesss-desc')


@echonestnonehandler
def get_songs(pyen, echonest_ids):
    return pyen.get('song/profile', track_id=echonest_ids,
                            bucket=['song_hotttnesss', 'id:spotify', 'audio_summary', 'tracks'])


@echonestnonehandler
def get_all_genres(pyen):
    return pyen.get('genre/list', results=1500)  # get all genres


@echonestnonehandler
def get_similar_genres(pyen, genre_name):
    return pyen.get('genre/similar', name=genre_name)


def _make_pyen(api_key):
    return pyen.Pyen(api_key)