import inspect
import os
from ordered_set import OrderedSet
from sqlalchemy import select as sqlselect, exists as sqlexists

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
os.sys.path.insert(0,parentdir)
from api import user_helper, db
from spotify import spotify_helper
from server import song_helper
from server.models import Artist, Song
from server import echonest_helper
from server.exceptions import EchonestApiObjectNotFoundException


def get_similar_artists(spotify_user_id, spotify_artist_id, force_update=False):
    _, genres_name = song_helper.db_load_genres()
    # get root artist and force update so we have roundtrip to spotify
    root_db_a = song_helper.transfer_artist_from_spotify(spotify_artist_id, genres_name, force_update=True)
    if root_db_a is None:
        return
    db.session.commit()
    user = user_helper.load_user(spotify_user_id)
    similar_artists = OrderedSet()
    sp_similar_artists = spotify_helper.get_similar_artists(user, spotify_artist_id)
    if sp_similar_artists is None:
        print('Artist id %s not found in Spotify(similar) anymore' % spotify_artist_id)
        song_helper.db_mark_artist_spotify_not_found(root_db_a.ArtistId)
        db.session.commit()
        # raise EchonestApiObjectNotFoundException(spotify_artist_id, 'id not found')
    else:
        for sp_artist in sp_similar_artists['artists']:
            db_a = song_helper.transfer_artist_from_spotify(sp_artist['uri'], genres_name)
            if db_a is not None:
                db.session.commit()
                similar_artists.add(db_a.ArtistId)
    song_helper.db_update_similar_artists(root_db_a.ArtistId, similar_artists, overwrite=True)
    db.session.commit()


def gather_similar_artists(spotify_user_id):
    # find similar artists for all not checked in db
    s = sqlselect([Artist.SpotifyId]).where((Artist.SimilarArtistsUpdatedAt == None) &
                                            (sqlexists().where(Artist.ArtistId == Song.ArtistId)))
    rows = db.session.execute(s).fetchall()
    for row in rows:
        get_similar_artists(spotify_user_id, row[0])


if __name__ == '__main__':
    # set api client helpers to server mode
    spotify_helper.refresh_token_on_expired = True
    spotify_helper.return_None_on_not_found = True
    echonest_helper.return_None_on_not_found = True
    # get_similar_artists('rudolfix-us', 'spotify:artist:6Ma3X8b9TtSSKjFehyI4ez')
    gather_similar_artists('rudolfix-us')