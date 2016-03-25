# crawl echo nest api and store songs information from top genres
from api import app, db
from api.models import Genre, Artist, Song, ArtistGenres, SongTracks
import pyen
import pickle
import time
import os
import unicodedata
# get top artists with top songs in genre
# http://developer.echonest.com/api/v4/genre/artists?api_key=UFIOCP1DHXIKUMV2H&format=json&results=5&bucket=hotttnesss&name=abstract+hip+hop&bucket=songs
# get all genres
# http://developer.echonest.com/api/v4/genre/list?api_key=UFIOCP1DHXIKUMV2H&format=json&start=0&results=1500
# get songs with audio_summary (max 2 songs)
# http://developer.echonest.com/api/v4/song/profile?api_key=UFIOCP1DHXIKUMV2H&id=SOLUXOH13692207BEF&id=SOKJIZT1311AFE7DAE&format=json&bucket=audio_summary&bucket=id:spotify
# get hottest songs in genre
# http://developer.echonest.com/api/v4/song/search?api_key=UFIOCP1DHXIKUMV2H&format=json&start=100&results=10&style=abstract+hip+hop&sort=song_hotttnesss-desc


_CHECK_ARTISTS_FILE = '.check_artists'
_CURRENT_GENRE_FILE = '.current_genre'


def convert_check_artists():
    with open(_CHECK_ARTISTS_FILE, 'br') as f:
        check_artists = pickle.load(f)
        def p2t(p):
            db.session.add(p[1])
            return p[0], p[1].ArtistId, p[1].EchonestId
        check_artists = [(p2t(p)) for p in check_artists]
    with open(_CHECK_ARTISTS_FILE, 'bw+') as f:
        pickle.dump(check_artists, f, protocol=0) # save in ASCII protocol


def gather_top_songs(check_top_artists=10, check_top_artist_songs=50):
    # check if zip with artists and genres is present, if so go to songs stage
    if os.path.isfile(_CHECK_ARTISTS_FILE):
        with open(_CHECK_ARTISTS_FILE, 'br') as f:
            check_artists = pickle.load(f)
        # optionaly remove all processed genres
        cg = None
        if os.path.isfile(_CURRENT_GENRE_FILE):
            with open(_CURRENT_GENRE_FILE, 'br') as f:
                cg = int(f.readline())

        filtered_artists = []
        add = cg is None # when none be in add mode from a start
        for gid, a_id, e_id in check_artists:
            if gid == cg:
                add = True
            if add:
                filtered_artists.append((gid, a_id, e_id))

        check_artists = filtered_artists
    else:
        check_artists = gather_genres_and_artists(check_top_artists)
    save_top_songs(check_artists, check_top_artist_songs)


def gather_genres_and_artists(check_top_artists):
    genres_id, genres_name = load_genres()
    print('got %i existing genres from database' % len(genres_id))
    # get all genres
    en = pyen.Pyen(app.config['ECHONEST_API_KEY'])
    genres = en.get('genre/list', results=1500)  # get all genres
    # write unknown genres to db
    new_genres = 0
    for g in genres['genres']:
        if g['name'] not in genres_name:
            db_g = Genre(Name=g['name'])
            db.session.add(db_g)
            new_genres += 1
    db.session.commit()
    print('inserted %i new genres to db' % new_genres)
    genres_id, genres_name = load_genres()
    # enumerate genres and gather all artist ids to check, insert artists to db
    check_artists = []
    for g_name in genres_name:
        while True:
            try:
                artists = en.get('genre/artists', results=check_top_artists, name=g_name, bucket=['hotttnesss',
                                 'id:spotify', 'genre'])
                break
            except Exception as exc:
                print(exc)
                print('will try again')
                time.sleep(20)
        print('got %i artists for genre %s' % (len(artists), g_name))
        for artist in artists['artists']:
            # check if list contains
            if any(artist['id'] in a for a in check_artists):
                print('artist %s(%s) is already on the list' % (artist['name'], artist['id']))
            # check if exists
            db_a = db.session.query(Artist).filter(Artist.EchonestId == artist['id']).one_or_none()
            if not db_a:
                if 'foreign_ids' in artist:
                    db_a = Artist(Name=artist['name'], SpotifyId=artist['foreign_ids'][0]['foreign_id'],
                                  Hotness=artist['hotttnesss'], EchonestId=artist['id'])
                    db_a.Genres = [ArtistGenres(GenreId=genres_name[n['name']]) for n in artist['genres']]
                    o = 1
                    for db_ag in db_a.Genres:
                        db_ag.Ord = o
                        o += 1
                    db.session.add(db_a)
                    print('artist %s NOT found in db, added with %i genres' % (db_a.Name, len(db_a.Genres)))
                else:
                    print('artist %s no spotifyID skipped' % artist['name'])
            else:
                print('artist %s FOUND in db, added with %i genres' % (db_a.Name, len(db_a.Genres)))
            if db_a:
                check_artists.append((genres_name[g_name], db_a))
        db.session.commit()
        print('commited artists')
    with open('check_artists', 'bw') as f:
        pickle.dump(check_artists, f, protocol=0) # save in ASCII protocol

    return [(p[0], p[1].ArtistId, p[1].EchonestId) for p in check_artists]


def save_top_songs(check_artists, check_top_artist_songs):
    # get hottest songs from the artists and store them in db
    spotify_dedup = {}
    en = pyen.Pyen(app.config['ECHONEST_API_KEY'])
    steps = -1
    for genre_id, artist_id, echo_id in check_artists:
        # save current genre
        steps += 1
        with open(_CURRENT_GENRE_FILE, 'w+') as f:
            f.write(str(genre_id))
        print('processing genre id %i, artists left %i' % (genre_id, len(check_artists) - steps))
        # get hottest songs for an artist (beware duplicate songs - check spotify id)
        # http://developer.echonest.com/api/v4/song/search?api_key=UFIOCP1DHXIKUMV2H&format=json&results=10&artist_id=AR6F6I21187FB5A3AA&sort=song_hotttnesss-desc&bucket=id:spotify&bucket=audio_summary
        while True:
            try:
                songs = en.get('song/search', results=check_top_artist_songs, artist_id=echo_id,
                               bucket=['song_hotttnesss', 'id:spotify', 'audio_summary', 'tracks'],
                               sort='song_hotttnesss-desc')
                break
            except Exception as exc:
                print(exc)
                print('will try again')
                time.sleep(20)

        processed_songs = {}
        for song in songs['songs']:
            # get all spotify ids
            spotify_ids = [SongTracks(SpotifyId=track['foreign_id'], EchonestId=track['id'])
                           for track in song['tracks']]
            # remove songs from the same artist with the same name
            if ci_s_normalize(song['title']) in processed_songs:
                # merge songs' tracks with the same name so no spotify id is lost
                orig_db_s = processed_songs[ci_s_normalize(song['title'])]
                # remove duplicates
                spotify_ids = [track for track in spotify_ids if track.SpotifyId not in
                               [t.SpotifyId for t in orig_db_s.Tracks]]
                orig_db_s.Tracks += spotify_ids
                print('Song %s already processed for this artist' % song['title'])
                continue
            # check if exists in spotify
            if len(spotify_ids) > 0:  # not in spotify_dedup
                db_s = db.session.query(Song).filter(Song.EchonestId == song['id']).one_or_none()
                if not db_s:
                    db_s = Song(Name=song['title'], Tracks=spotify_ids, Hotness=song['song_hotttnesss'],
                                EchonestId=song['id'], ArtistId=artist_id, GenreId=genre_id, IsToplistSong=1)
                    summary = song['audio_summary']
                    db_s.DurationMs = summary['duration']*1000
                    db_s.AS_key = summary['key']
                    db_s.AS_energy = summary['energy']
                    db_s.AS_liveness = summary['liveness']
                    db_s.AS_tempo = summary['tempo']
                    db_s.AS_speechiness = summary['speechiness']
                    db_s.AS_acousticness = summary['acousticness']
                    db_s.AS_instrumentalness = summary['instrumentalness']
                    db_s.AS_mode = summary['mode']
                    db_s.AS_time_signature = summary['time_signature']
                    db_s.AS_loudness = summary['loudness']
                    db_s.AS_valence = summary['valence']
                    db_s.AS_danceability = summary['danceability']
                    db.session.add(db_s)
                    print('song %s NOT found in db -> added' % db_s.Name)
                else:
                    print('song %s FOUND in db -> skipped' % db_s.Name)
                processed_songs[ci_s_normalize(db_s.Name)] = db_s
            else:
                print('song %s (%s) no spotifyID skipped' % (song['title'], song['id']))
        db.session.commit()
        print('commited songs')
    # cleanup
    os.remove(_CURRENT_GENRE_FILE)
    os.rename(_CHECK_ARTISTS_FILE, '.check_artists_done')


def ci_s_normalize(s):
    return unicodedata.normalize('NFKD', s.casefold())


def load_genres():
    genres_id = {}
    genres_name = {}
    for db_g in db.session.query(Genre):
        genres_id[db_g.GenreId] = db_g.Name
        genres_name[db_g.Name] = db_g.GenreId

    return genres_id, genres_name


def isnull(val, r):
    return val if val is not None else r


if __name__ == '__main__':
    gather_top_songs()
    # convert_check_artists()