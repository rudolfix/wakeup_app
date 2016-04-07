import datetime
import inspect
import itertools
import os
import re as regex
import unicodedata
from sqlalchemy import update as sqlupdate, insert as sqlinsert

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
os.sys.path.insert(0,parentdir)
from api import db
from server.models import Genre, Artist, Song, ArtistGenres, SongTracks, Group, SongGroup, SimilarArtist
from server.exceptions import *
from server import echonest_helper


def db_update_artist(pyen_artist, genres_name):
    if 'foreign_ids' not in pyen_artist:
        print('artist %s no spotifyID skipped' % pyen_artist['name'])
        return None
    # check if exists
    db_a = db_get_artist_by_echonest_id(pyen_artist['id'])
    if not db_a:
        db_a = Artist(SpotifyId=pyen_artist['foreign_ids'][0]['foreign_id'], EchonestId=pyen_artist['id'])
        db.session.add(db_a)
        print('artist %s NOT found in db, added with %i genres' % (pyen_artist['name'], len(pyen_artist['genres'])))
    else:
        print('artist %s FOUND in db, added with %i genres' % (pyen_artist['name'], len(pyen_artist['genres'])))
    db_a.Name = pyen_artist['name']
    db_a.Hotness = pyen_artist['hotttnesss']
    db_a.Genres[:] = []
    for o, n in enumerate(pyen_artist['genres']):
        db_a.Genres.append(ArtistGenres(GenreId=genres_name[n['name']], Ord=o))
    db_a.UpdatedAt = datetime.datetime.utcnow()

    return db_a


def db_update_song(pyen_song, db_artist_id, db_genre_id, song_type, processed_songs=None):
    processed_songs = processed_songs or {}
    # get all spotify ids
    spotify_ids = [SongTracks(SpotifyId=track['foreign_id'], EchonestId=track['id'])
                   for track in db_dedup_song_tracks(pyen_song['tracks'])]
    # check if exists in spotify
    if len(spotify_ids) == 0:
        print('song %s (%s) has no spotifyID or ids got deduped, skipped' % (pyen_song['title'], pyen_song['id']))
        return None
    # assert no duplicates in collection
    assert len(set([sid.SpotifyId for sid in spotify_ids])) == len(spotify_ids),\
        'duplicate spotify id for %s (%s)' % (pyen_song['title'], pyen_song['id'])
    # remove songs from the same artist with the same name
    if ci_s_normalize(pyen_song['title']) in processed_songs:
        # merge songs' tracks with the same name so no spotify id is lost
        orig_db_s = processed_songs[ci_s_normalize(pyen_song['title'])]
        # remove duplicates
        spotify_ids = [track for track in spotify_ids if track.SpotifyId not in
                       [t.SpotifyId for t in orig_db_s.Tracks]]
        orig_db_s.Tracks += spotify_ids
        print('Song %s (%s) already processed for this artist' % (pyen_song['title'], pyen_song['id']))
        return None

    print('Processing song %s (%s)' % (pyen_song['title'], pyen_song['id']))
    db_s = db.session.query(Song).filter(Song.EchonestId == pyen_song['id']).one_or_none()
    if not db_s:
        db_s = Song(Tracks=spotify_ids, EchonestId=pyen_song['id'], ArtistId=db_artist_id, GenreId=db_genre_id)
        db.session.add(db_s)
        print('song %s NOT found in db -> added' % pyen_song['title'])
    else:
        print('song %s FOUND in db -> updated' % pyen_song['title'])
    db_s.Name = pyen_song['title']
    db_s.Hotness = pyen_song['song_hotttnesss']
    db_s.IsToplistSong = song_type
    summary = pyen_song['audio_summary']
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
    db_s.UpdatedAt = datetime.datetime.utcnow()
    processed_songs[ci_s_normalize(db_s.Name)] = db_s

    return db_s


def db_get_artist_by_echonest_id(echonest_id):
    return db.session.query(Artist).filter(Artist.EchonestId == echonest_id).one_or_none()


def db_get_artist_by_spotify_id(spotify_id):
    return db.session.query(Artist).filter(Artist.SpotifyId == spotify_id).one_or_none()


def db_get_songs_by_spotify_ids(spotify_ids):
    return db.session.query(Song).join(Song.Tracks).filter(SongTracks.SpotifyId.in_(spotify_ids)).all()


def db_get_song_group_by_uniqref(uniq_ref):
    return db.session.query(Group).filter(Group.UniqueRef == uniq_ref).one_or_none()


def db_load_genres():
    genres_id = {}
    genres_name = {}
    for db_g in db.session.query(Genre):
        genres_id[db_g.GenreId] = db_g.Name
        genres_name[db_g.Name] = db_g.GenreId

    return genres_id, genres_name


def db_dedup_song_tracks(tracks):
    dedup = []
    for track in tracks:
        if db.session.query(SongTracks).filter(SongTracks.SpotifyId == track['foreign_id']).one_or_none() is None:
            dedup.append(track)
    return dedup


def db_create_song_group(group_name, group_uniq_ref, group_type, overwrite=False):
    db_g = db_get_song_group_by_uniqref(group_uniq_ref)
    if db_g is None:
        db_g = Group(UniqueRef=group_uniq_ref)
        db.session.add(db_g)
    elif overwrite:
        db.session.query(SongGroup).filter(SongGroup.GroupId == db_g.GroupId).delete()
    else:
        raise SongGroupExistsException(group_name)
    db_g.Name = remove_utf84b(group_name)
    db_g.Type = group_type
    return db_g


def db_update_songs_group(group_id, song_ids, overwrite=False):
    if overwrite:
        db.session.query(SongGroup).filter(SongGroup.GroupId == group_id).delete()
    for order, song_id in enumerate(song_ids):
        db_sg = SongGroup(SongId=song_id, GroupId=group_id, Ord=order)
        db.session.add(db_sg)


def db_update_similar_artists(artist_id, similar_artist_ids, overwrite=False):
    if overwrite:
        db.session.query(SimilarArtist).filter(SimilarArtist.ArtistId == artist_id).delete()
    # directly update with inserts without object creation
    ins_v = []
    for dist, s_a_id in enumerate(similar_artist_ids):
        ins_v.append({'ArtistId': artist_id, 'SimilarArtistId': s_a_id, 'Dist': dist})
    if len(ins_v) > 0:
        db.session.execute(sqlinsert(SimilarArtist), ins_v)
    # update timestamp
    stmt = sqlupdate(Artist).where(Artist.ArtistId == artist_id)\
        .values(SimilarArtistsUpdatedAt=datetime.datetime.utcnow())
    db.session.execute(stmt)


def db_mark_artist_spotify_not_found(artist_id):
    db.session.execute(sqlupdate(Artist).where(Artist.ArtistId == artist_id).values(SpotifyStatus=-1))


def transfer_songs_from_spotify(spotify_ids, genres_name=None, song_type=None, force_update=False):
    processed_songs = {}  # return all newly added or existing songs
    db_songs = []
    # translate spotify_id -> echonest_id by loading songs from DB
    if not force_update:
        db_songs = db_get_songs_by_spotify_ids(spotify_ids)
        for db_s in db_songs:
            processed_songs[ci_s_normalize(db_s.Name)] = db_s
        # remove spotify ids already in db
        check_spotify_ids = [track for track in spotify_ids if track not in
                            [t.SpotifyId for t in itertools.chain(*[db_s.Tracks for db_s in db_songs])]]
    else:
        check_spotify_ids = spotify_ids[:]

    # get multiple tracks
    if genres_name is None:
        _, genres_name = db_load_genres()
    for chunk in chunks(check_spotify_ids, 100):
        songs = echonest_helper.get_songs(chunk) or {'songs': []}
        for song in songs['songs']:
            # check if artist exists
            db_a = db_get_artist_by_echonest_id(song['artist_id'])
            if db_a is None:
                # get artist
                artist = echonest_helper.get_artist(song['artist_id'])
                db_a = db_update_artist(artist, genres_name)
                db.session.commit()
            # write song
            if db_a is not None:
                # todo: we may allow artists without spotify reference so we can process more songs
                genre_id = db_a.Genres[0].GenreId if db_a.Genres is not None and len(db_a.Genres) > 0 else None
                db_s = db_update_song(song, db_a.ArtistId, genre_id, song_type=song_type,
                                      processed_songs=processed_songs)
                if db_s is not None:  # duplicate songs and songs without spotify reference are skipped
                    db_songs.append(db_s)
                    db.session.commit()
    # return songs in list order, songs may have
    found_songs = []; not_found_songs = []
    # indexed_songs = {}
    # todo: this is O(n) ;/ - make it olog(n) by storing tracks in dict, it may be slow because it loads tracks from db
    for sp_id in spotify_ids:
        db_s = get_first(db_songs, lambda x: sp_id in [t.SpotifyId for t in x.Tracks])
        if db_s is not None:
            found_songs.append(db_s)
            db_songs.remove(db_s)  # prevent duplicates
        else:
            not_found_songs.append(sp_id)
    return found_songs, not_found_songs


def transfer_artist_from_spotify(spotify_id, genres_name, force_update=False):
    if not force_update:
        # check if artist exists
        db_a = db_get_artist_by_spotify_id(spotify_id)
        if db_a is not None:
            return db_a
    # get artist from echonest and update in db
    artist = echonest_helper.get_artist(spotify_id)
    if artist is None:
        print('spotify artist %s does not exist in echonest' % spotify_id)
        return None
    return db_update_artist(artist, genres_name)


def update_genres_from_echonest():
    # get all genres
    _, genres_name = db_load_genres()
    print('got %i existing genres from database' % len(genres_name))
    genres = echonest_helper.get_all_genres()
    # write unknown genres to db
    new_genres = 0
    for g in genres['genres']:
        if g['name'] not in genres_name:
            db_g = Genre(Name=g['name'])
            db.session.add(db_g)
            new_genres += 1
    return new_genres


def ci_s_normalize(s):
    return unicodedata.normalize('NFKD', s.casefold())


def isnull(val, r):
    return val if val is not None else r


def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i+n]


def get_first(iterable, f):
    for item in iterable or []:
        if f(item):
            return item
    return None


re_pattern = regex.compile(u'[^\u0000-\uD7FF\uE000-\uFFFF]', regex.UNICODE)


def remove_utf84b(str):
    return re_pattern.sub(u'\uFFFD', str)