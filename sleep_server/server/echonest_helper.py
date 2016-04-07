import pyen
import inspect
import os
from functools import wraps

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
os.sys.path.insert(0,parentdir)
from api import app
from server.exceptions import *


return_None_on_not_found = False


def echonestnonehandler(f):
    @wraps(f)
    def _wrap(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except pyen.PyenException as pyen_exc:
            # code == 5 -> invalid parameter but also means not found
            if pyen_exc.code == 5:
                if return_None_on_not_found:
                    return None
                else:
                    raise EchonestApiObjectNotFoundException(pyen_exc.code, pyen_exc.msg)
            raise
    return _wrap


@echonestnonehandler
def get_artist(any_id):
    return _make_pyen().get('artist/profile', id=any_id, bucket=['hotttnesss','id:spotify', 'genre'])['artist']


@echonestnonehandler
def get_artists_in_genre(genre_name, check_top_artists):
    return _make_pyen().get('genre/artists', results=check_top_artists, name=genre_name, bucket=['hotttnesss',
                                                                                                 'id:spotify', 'genre'])


@echonestnonehandler
def get_top_songs_for_artist(artist_id, check_top_artist_songs):
    return _make_pyen().get('song/search', results=check_top_artist_songs, artist_id=artist_id,
                            bucket=['song_hotttnesss', 'id:spotify', 'audio_summary', 'tracks'],
                            sort='song_hotttnesss-desc')


@echonestnonehandler
def get_songs(echonest_ids):
    return _make_pyen().get('song/profile', track_id=echonest_ids,
                            bucket=['song_hotttnesss', 'id:spotify', 'audio_summary', 'tracks'])


@echonestnonehandler
def get_all_genres():
    return _make_pyen().get('genre/list', results=1500)  # get all genres


def _make_pyen():
    return pyen.Pyen(app.config['ECHONEST_API_KEY'])