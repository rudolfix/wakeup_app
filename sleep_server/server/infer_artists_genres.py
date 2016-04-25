import inspect
import os
from sqlalchemy import text as sqltext

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
os.sys.path.insert(0, parentdir)
from server import db
from server import song_helper


def test_infer_genres_with_reimport(echo_artist_id):
    db_a = song_helper.db_get_artist_by_echonest_id(echo_artist_id)
    print(db_a.Genres)
    artists_genres = song_helper.db_get_all_artists_genres()
    similar_ids = song_helper.db_get_similar_artists(db_a.ArtistId)
    song_helper.infer_and_store_genres_for_artist(db_a.ArtistId, similar_ids, artists_genres)
    _, genres_name = song_helper.db_get_genres()
    # test artist update to see if genres are not overwritten
    db_a = song_helper.db_get_artist_by_echonest_id(echo_artist_id)
    print(db_a.Genres)
    song_helper.transfer_artist(db_a.SpotifyId, genres_name, force_update=True)
    db_a = song_helper.db_get_artist_by_echonest_id(echo_artist_id)
    print(db_a.Genres)


def infer_genres(dry_run=False):
    artists_genres = song_helper.db_get_all_artists_genres()
    # get all artists with no genres but with similar artists
    s = sqltext('SELECT a.ArtistId FROm Artists a WHERE '
                'NOT EXISTS(SELECT 1 FROM ArtistGenres ag WHERE ag.ArtistId = a.ArtistId) AND '
                'EXISTS (SELECT 1 FROM SimilarArtists sa WHERE sa.ArtistId = a.ArtistId)')
    to_infer = [row[0] for row in db.session.execute(s)]
    cnt = len(to_infer)
    print('Inferring %i artists' % cnt)
    if dry_run:
        return
    for artist_id in to_infer:
        similar_ids = song_helper.db_get_similar_artists(artist_id)
        song_helper.infer_and_store_genres_for_artist(artist_id, similar_ids, artists_genres)
        cnt -= 1
        if cnt % 100 == 0:
            print('%i artists left' % cnt)


if __name__ == '__main__':
    # test_infer_genres_with_reimport('ARTSENB12D4DEAE300')
    infer_genres(dry_run=False)

