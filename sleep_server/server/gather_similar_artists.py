import inspect
import os
import time
from sqlalchemy import select as sqlselect, exists as sqlexists, text as sqltext

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
os.sys.path.insert(0, parentdir)
from common import spotify_helper
from server import db, song_helper, echonest_helper
from server.models import Artist, Song
from common.user_base import UserBase


def process_rows(user, genres_name, rows, force_update):
    cnt = len(rows)
    print('will process %i artists' % cnt)
    for row in rows:
        # get root artist and force update so we have roundtrip to spotify
        try:
            root_db_a, _ = song_helper.transfer_artist(row[0], genres_name, force_update=force_update)
            if root_db_a is not None:
                song_helper.transfer_similar_artists(user, root_db_a, genres_name)
        except Exception as exc:
            print(exc)
            print('will try again')
            time.sleep(20)
        cnt -= 1
        if cnt % 10 == 0:
            print('%i artists left' % cnt)
    print('done')


def gather_similar_artists_with_songs(user, genres_name, force_update):
    s = sqlselect([Artist.SpotifyId]).where((Artist.SimilarArtistsUpdatedAt == None) &
                                            (sqlexists().where(Artist.ArtistId == Song.ArtistId)))
    process_rows(user, genres_name, db.session.execute(s).fetchall(),force_update)


def gather_similar_artists(user, genres_name, force_update):
    # find similar artists for all not checked in db
    s = sqlselect([Artist.SpotifyId]).where(Artist.SimilarArtistsUpdatedAt == None)
    process_rows(user, genres_name, db.session.execute(s).fetchall(), force_update)


def gather_similar_artists_with_genres(user, genres_name, force_update):
    # find similar artists for all not checked in db
    s = sqlselect([Artist.SpotifyId], sqltext('EXISTS (SELECT 1 FROM ArtistGenres ag WHERE ag.ArtistId = '
                                                        'Artists.ArtistId AND ag.SourceType = 1)'))\
        .where(Artist.SimilarArtistsUpdatedAt == None)
    process_rows(user, genres_name, db.session.execute(s).fetchall(), force_update)


def gather_similar_artists_for_group(user, genres_name, group_id, force_update):
    s = sqltext('SELECT a.SpotifyId FROM Artists a WHERE EXISTS '
                '(SELECT 1 FROM Songs s JOIN SongGroups sg ON s.SongId = sg.SongId '
                'WHERE a.ArtistId = s.ArtistId AND sg.GroupId = %i)' % group_id) # AND a.SimilarArtistsUpdatedAt IS NULL

    process_rows(user, genres_name, db.session.execute(s).fetchall(), force_update)


def gather_similar_artists_for_group_type(user, genres_name, group_type, force_update):
    s = sqltext('SELECT a.SpotifyId FROM Artists a WHERE EXISTS '
                '(SELECT 1 FROM Songs s JOIN SongGroups sg ON s.SongId = sg.SongId '
                'JOIN Groups g ON g.GroupId = sg.GroupId '
                'WHERE a.ArtistId = s.ArtistId AND g.Type = %i AND a.SimilarArtistsUpdatedAt IS NULL)' % group_type)

    process_rows(user, genres_name, db.session.execute(s).fetchall(), force_update)


if __name__ == '__main__':
    # set api client helpers to server mode
    spotify_helper.refresh_token_on_expired = True
    spotify_helper.return_None_on_not_found = True
    echonest_helper.return_None_on_not_found = True
    #gather_similar_artists_for_group_type('rudolfix-us', 1)
    _, genres_name = song_helper.db_get_genres()
    user = UserBase.from_file('test_accounts/rudolfix-us.json')
    gather_similar_artists(user, genres_name, False)
    # get_similar_artists('rudolfix-us', 'spotify:artist:6Ma3X8b9TtSSKjFehyI4ez')
    # gather_similar_artists_for_group('rudolfix-us', 66)