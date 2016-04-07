# crawl echo nest api and store songs information from top genres
import inspect
from operator import itemgetter
import pickle
import time
import os
from sqlalchemy import select as sqlselect

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
os.sys.path.insert(0,parentdir)
from api import app, db
from server import song_helper, echonest_helper
from server.models import Artist, ArtistGenres

# get top artists with top songs in genre
# http://developer.echonest.com/api/v4/genre/artists?api_key=UFIOCP1DHXIKUMV2H&format=json&results=5&bucket=hotttnesss&name=abstract+hip+hop&bucket=songs
# get all genres
# http://developer.echonest.com/api/v4/genre/list?api_key=UFIOCP1DHXIKUMV2H&format=json&start=0&results=1500
# get songs with audio_summary (max 2 songs)
# http://developer.echonest.com/api/v4/song/profile?api_key=UFIOCP1DHXIKUMV2H&id=SOLUXOH13692207BEF&id=SOKJIZT1311AFE7DAE&format=json&bucket=audio_summary&bucket=id:spotify
# get hottest songs in genre
# http://developer.echonest.com/api/v4/song/search?api_key=UFIOCP1DHXIKUMV2H&format=json&start=100&results=10&style=abstract+hip+hop&sort=song_hotttnesss-desc


_CHECK_ARTISTS_FILE = '.check_artists'
_CURRENT_ARTIST_FILE = '.current_artist'


def convert_check_artists():
    with open(_CHECK_ARTISTS_FILE, 'br') as f:
        check_artists = pickle.load(f)
        def p2t(p):
            db.session.add(p[1])
            return p[0], p[1].ArtistId, p[1].EchonestId
        check_artists = [(p2t(p)) for p in check_artists]
    with open(_CHECK_ARTISTS_FILE, 'bw+') as f:
        pickle.dump(check_artists, f, protocol=0) # save in ASCII protocol


def gather_genres_and_artists(check_top_artists):
    new_genres = song_helper.update_genres_from_echonest()
    db.session.commit()
    print('inserted %i new genres to db' % new_genres)
    genres_id, genres_name = song_helper.db_load_genres()

    # enumerate genres and gather all artist ids to check, insert artists to db
    check_artists = []
    for g_name in genres_name:
        while True:
            try:
                artists = echonest_helper.get_artists_in_genre(g_name, check_top_artists)
                break
            except Exception as exc:
                print(exc)
                print('will try again')
                time.sleep(20)
        print('got %i artists for genre %s' % (len(artists['artists']), g_name))
        for artist in artists['artists']:
            # check if list contains
            if any(artist['id'] in a for a in check_artists):
                print('artist %s(%s) is already on the list' % (artist['name'], artist['id']))
            db_a = song_helper.db_update_artist(artist, genres_name)
            if db_a:
                check_artists.append((genres_name[g_name], db_a))
        db.session.commit()
    # extract required info from sqlalchemy objects
    check_artists = sorted([(p[0], p[1].ArtistId, p[1].EchonestId) for p in check_artists], key=itemgetter(1))
    # save collection sorted by artist ids
    with open(_CHECK_ARTISTS_FILE, 'bw') as f:
        pickle.dump(check_artists, f, protocol=0) # save in ASCII protocol

    return check_artists


def gather_artists_from_db(_):
    # get all artist genres
    s = sqlselect([ArtistGenres.GenreId, ArtistGenres.ArtistId]).order_by(ArtistGenres.ArtistId)\
                                                                .order_by(ArtistGenres.Ord)
    rows = db.session.execute(s).fetchall()
    a_genres = {}
    for row in rows:
        if row[1] not in a_genres:
            a_genres[row[1]] = row[0]
    # get all artists from db
    s = sqlselect([Artist.ArtistId, Artist.EchonestId])
    check_artists = []
    rows = db.session.execute(s).fetchall()
    for row in rows:
        g_id = a_genres[row[0]] if row[0] in a_genres else None
        check_artists.append((g_id, row[0], row[1]))
    # save and return
    check_artists = sorted(check_artists, key=itemgetter(1))
    with open(_CHECK_ARTISTS_FILE, 'bw') as f:
        pickle.dump(check_artists, f, protocol=0) # save in ASCII protocol

    return check_artists


def save_top_songs(check_artists, check_top_artist_songs, is_top_list = 1):
    # get hottest songs from the artists and store them in db
    steps = -1
    for genre_id, artist_id, echo_id in check_artists:
        # save current artist
        steps += 1
        with open(_CURRENT_ARTIST_FILE, 'w+') as f:
            f.write(str(artist_id))
        print('processing genre id %i, artists left %i' % (genre_id, len(check_artists) - steps))
        # get hottest songs for an artist (beware duplicate songs - check spotify id)
        # http://developer.echonest.com/api/v4/song/search?api_key=UFIOCP1DHXIKUMV2H&format=json&results=10&artist_id=AR6F6I21187FB5A3AA&sort=song_hotttnesss-desc&bucket=id:spotify&bucket=audio_summary
        while True:
            try:
                songs = echonest_helper.get_top_songs_for_artist(echo_id, check_top_artist_songs)
                break
            except Exception as exc:
                print(exc)
                print('will try again')
                time.sleep(20)

        processed_songs = {}
        for song in songs['songs']:
            song_helper.db_update_song(song, artist_id, genre_id, is_top_list, processed_songs)

        # whole artist must be written at once
        db.session.commit()
        print('commited songs')

    # cleanup
    os.remove(_CURRENT_ARTIST_FILE)
    os.rename(_CHECK_ARTISTS_FILE, '.check_artists_done')


def gather_top_songs(artist_provider, check_top_artists=15, check_top_artist_songs=100, is_top_list=1):
    # check if zip with artists and genres is present, if so go to songs stage
    if os.path.isfile(_CHECK_ARTISTS_FILE):
        with open(_CHECK_ARTISTS_FILE, 'br') as f:
            check_artists = pickle.load(f)
        # optionaly remove all processed genres
        ca = None
        if os.path.isfile(_CURRENT_ARTIST_FILE):
            with open(_CURRENT_ARTIST_FILE, 'br') as f:
                ca = int(f.readline())

        filtered_artists = []
        add = ca is None # when none, be in add mode from a start
        for gid, a_id, e_id in check_artists:
            if a_id == ca:
                add = True
            if add:
                filtered_artists.append((gid, a_id, e_id))

        check_artists = filtered_artists
    else:
        check_artists = artist_provider(check_top_artists)
    save_top_songs(check_artists, check_top_artist_songs)


if __name__ == '__main__':
    # server mode for echonest client
    echonest_helper.return_None_on_not_found = True
    #gather_top_songs(gather_genres_and_artists, is_top_list = 1)
    gather_top_songs(gather_artists_from_db, is_top_list=0)
    # convert_check_artists()