from ordered_set import OrderedSet
from sqlalchemy import update as sqlupdate, insert as sqlinsert, select as sqlselect, text as sqltext
from operator import itemgetter
import math

from common.common import *
from common import spotify_helper
from server import db
from server.models import Genre, Artist, Song, ArtistGenres, SongTracks, Group, SongGroup, SimilarArtist,\
    GenreSourceType, SimilarGenre, ArtistAdditionalSpotifyIds
from server.exceptions import *
from server import echonest_helper

_song_sel_columns = [Song.AS_energy, Song.AS_liveness, Song.AS_tempo, Song.AS_speechiness, Song.AS_acousticness,
                     Song.AS_instrumentalness, Song.AS_loudness, Song.AS_valence, Song.AS_danceability, Song.AS_key,
                     Song.AS_mode, Song.AS_time_signature, Song.DurationMs, Song.SongId, Song.GenreId, Song.ArtistId]


def db_update_artist(pyen_artist, genres_name, additional_spotify_id=None):
    if 'foreign_ids' not in pyen_artist:
        if additional_spotify_id is None:
            print('artist %s no spotifyID skipped' % pyen_artist['name'])
            return None
        else:
            # it often happens that spotify id is resolved but then not included in echonest artist
            artist_sp_id = additional_spotify_id
    else:
        artist_sp_id = pyen_artist['foreign_ids'][0]['foreign_id']
    # check if exists
    db_a = db_get_artist_by_echonest_id(pyen_artist['id'])
    if not db_a:
        db_a = Artist(SpotifyId=artist_sp_id, EchonestId=pyen_artist['id'])
        db.session.add(db_a)
        print('artist %s NOT found in db, added with %i genres' % (pyen_artist['name'], len(pyen_artist['genres'])))
    else:
        print('artist %s FOUND in db, added with %i genres' % (pyen_artist['name'], len(pyen_artist['genres'])))
    db_a.Name = pyen_artist['name']
    db_a.Hotness = pyen_artist['hotttnesss']
    # write genres only when they exist, do not touch otherwise as Genres may be inferred
    if len(pyen_artist['genres']) > 0:
        db_a.Genres[:] = []
        for o, n in enumerate(pyen_artist['genres']):
            db_a.Genres.append(ArtistGenres(GenreId=genres_name[n['name']], Ord=o,
                                            SourceType=GenreSourceType.echonest.value))
    db_a.UpdatedAt = datetime.utcnow()
    if additional_spotify_id is not None and db_a.SpotifyId != additional_spotify_id:
        # artists may have many spotify ids (all mapping to the same object), store those ids in sep table
        if not any(filter(lambda add_id: add_id.SpotifyId == additional_spotify_id, db_a.AdditionalSpotifyIds)):
            print('artist %s has ADDITIONAL spotify id %s' % (pyen_artist['name'], additional_spotify_id))
            db_a.AdditionalSpotifyIds.append(ArtistAdditionalSpotifyIds(SpotifyId=additional_spotify_id))

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
    song_dedup_name = normalized_song_dedup_name(db_artist_id, pyen_song['title'])
    if song_dedup_name in processed_songs:
        # merge songs' tracks with the same name so no spotify id is lost
        orig_db_s = processed_songs[song_dedup_name]
        # remove duplicates
        spotify_ids = [track for track in spotify_ids if track.SpotifyId not in
                       [t.SpotifyId for t in orig_db_s.Tracks]]
        orig_db_s.Tracks += spotify_ids
        print('Song %s (%s) already processed for this artist' % (song_dedup_name, pyen_song['id']))
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
    db_s.UpdatedAt = datetime.utcnow()
    processed_songs[song_dedup_name] = db_s

    return db_s


def db_get_artist_by_echonest_id(echonest_id):
    return db.session.query(Artist).filter(Artist.EchonestId == echonest_id).one_or_none()


def db_get_artist_by_spotify_id(spotify_id):
    return db.session.query(Artist).filter(Artist.SpotifyId == spotify_id).one_or_none() or \
           db.session.query(ArtistAdditionalSpotifyIds).filter(ArtistAdditionalSpotifyIds.SpotifyId == spotify_id).one_or_none()


def db_get_songs_by_spotify_ids(spotify_ids):
    return db.session.query(Song).join(Song.Tracks).filter(SongTracks.SpotifyId.in_(spotify_ids)).all()


def db_get_song_group_by_uniqref(uniq_ref):
    return db.session.query(Group).filter(Group.UniqueRef == uniq_ref).one_or_none()


def db_get_genres():
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
        .values(SimilarArtistsUpdatedAt=datetime.utcnow())
    db.session.execute(stmt)


def db_mark_artist_spotify_not_found(artist_id):
    db.session.execute(sqlupdate(Artist).where(Artist.ArtistId == artist_id).values(SpotifyStatus=-1))


def db_get_song_ids_for_tracks_by_spotify_ids(spotify_ids):
    indexed_songs = {}
    for row in db.session.execute(sqlselect([SongTracks.SpotifyId, SongTracks.SongId],
                                            SongTracks.SpotifyId.in_(spotify_ids))).fetchall():
        indexed_songs[row[0]] = row[1]
    return indexed_songs


def db_get_spotify_track_ids_for_songs(song_ids):
    indexed_songs = {}
    for row in db.session.execute(sqlselect([SongTracks.SpotifyId, SongTracks.SongId],
                                            SongTracks.SongId.in_(song_ids))).fetchall():
        indexed_songs[row[0]] = row[1]
    return indexed_songs


def db_get_all_artists_genres(genre_source_types=None):
    genre_source_types = genre_source_types or [GenreSourceType.echonest.value]
    s = sqlselect([ArtistGenres.GenreId, ArtistGenres.ArtistId], ArtistGenres.SourceType.in_(genre_source_types))\
        .order_by(ArtistGenres.ArtistId).order_by(ArtistGenres.Ord)
    rows = db.session.execute(s).fetchall()
    a_genres = {}
    for row in rows:
        if row[1] not in a_genres:
            a_genres[row[1]] = [row[0]]
        else:
            a_genres[row[1]].append(row[0])
    return a_genres


def db_get_genres_for_artists(artist_ids, genre_source_types=None):
    genre_source_types = genre_source_types or [GenreSourceType.echonest.value]
    s = sqlselect([ArtistGenres.GenreId, ArtistGenres.ArtistId], ArtistGenres.SourceType.in_(genre_source_types) &
                  ArtistGenres.ArtistId.in_(artist_ids))\
        .order_by(ArtistGenres.ArtistId).order_by(ArtistGenres.Ord)
    rows = db.session.execute(s).fetchall()
    a_genres = {}
    for row in rows:
        if row[1] not in a_genres:
            a_genres[row[1]] = [row[0]]
        else:
            a_genres[row[1]].append(row[0])
    return a_genres


def db_get_similar_artists(artist_id):
    s = sqlselect([SimilarArtist.SimilarArtistId], SimilarArtist.ArtistId == artist_id).order_by(SimilarArtist.Dist)
    rows = db.session.execute(s).fetchall()
    return [row[0] for row in rows]


def db_update_artist_genres(artist_id, genres, source_type, update_songs=True):
    db.session.query(ArtistGenres).filter(ArtistGenres.ArtistId == artist_id).delete()
    # directly update with inserts without object creation
    ins_v = []
    for gid, o in genres:
        ins_v.append({'ArtistId': artist_id, 'GenreId': gid, 'Ord': o, 'SourceType': source_type})
    if len(ins_v) > 0:
        db.session.execute(sqlinsert(ArtistGenres), ins_v)
    # update all artists song if necessary
    if update_songs and len(genres) > 0:
        stmt = sqlupdate(Song).where(Song.ArtistId == artist_id).values(GenreId=genres[0][0])
        db.session.execute(stmt)


def db_update_similar_genres(genre_id, similar_genres):
    db.session.query(SimilarGenre).filter(SimilarGenre.GenreId == genre_id).delete()
    # directly update with inserts without object creation
    ins_v = []
    for gid, sim in similar_genres:
        ins_v.append({'GenreId': genre_id, 'SimilarGenreId': gid, 'Similarity': sim})
    if len(ins_v) > 0:
        db.session.execute(sqlinsert(SimilarGenre), ins_v)


def db_get_artists_name(artist_id):
    s = sqlselect([Artist.Name], Artist.ArtistId == artist_id)
    row = db.session.execute(s).fetchone()
    return row[0]


def db_make_song_selector_from_list(song_ids):
    return sqlselect(_song_sel_columns, Song.SongId.in_(song_ids))


def db_make_song_selector_for_genre(genre_id, max_duration_ms, limit, genre_source_types=None, significant_genres=4):
    # todo: write this SQL in alchemy (which is ridiculous)
    gst = genre_source_types or ['1', '2'] #  GenreSourceType.echonest.value, GenreSourceType.infered.value
    song_in_genre_q = " Songs.DurationMs < %i AND EXISTS (SELECT 1 FROM Artists a JOIN ArtistGenres ag ON a.ArtistId "\
                  "= ag.ArtistId WHERE a.ArtistId = Songs.ArtistId AND ag.GenreId = %i AND ag.Ord < %i AND ag.SourceType IN (%s) )"
    return sqlselect(_song_sel_columns)\
        .where(sqltext(song_in_genre_q % (max_duration_ms, genre_id, significant_genres, ','.join(gst))))\
        .order_by(Song.Hotness.desc()).limit(limit)


def db_make_song_selector_top_songs():
    return sqlselect(_song_sel_columns, Song.IsToplistSong == 1)


def db_select_song_rows(selector):
    # selector is just an SQL string
    return db.session.execute(selector).fetchall()


def transfer_songs(track_mappings, genres_name, song_type=None, force_update=False, chunk_size=100):
    processed_songs = {}  # return all newly added or existing songs
    db_songs = []
    new_artists = []
    indexed_songs = {}
    # translate spotify_id -> echonest_id by loading songs from DB
    if not force_update:
        spotify_ids = [m[0] for m in track_mappings]
        db_songs = db_get_songs_by_spotify_ids(spotify_ids)
        for db_s in db_songs:
            processed_songs[normalized_song_dedup_name(db_s.ArtistId, db_s.Name)] = db_s
        # remove spotify ids already in db
        indexed_songs = db_get_spotify_track_ids_for_songs([s.SongId for s in db_songs])
        check_mappings = [mapping for mapping in track_mappings if mapping[0] not in indexed_songs]
    else:
        check_mappings = track_mappings[:]

    # get multiple tracks
    for chunk in list_chunker(check_mappings, chunk_size):
        songs = echonest_helper.get_songs([m[0] for m in chunk]) or {'songs': []}
        for song in songs['songs']:
            # check if artist exists
            db_a = db_get_artist_by_echonest_id(song['artist_id'])
            if db_a is None:
                # get artist
                artist = echonest_helper.get_artist(song['artist_id'])
                # if artist has no foreign id try to get spotify artist id from mappings
                additional_spotify_id = None
                if 'foreign_ids' not in artist:
                    song_foreign_ids = [t['foreign_id'] for t in song['tracks'] if 'foreign_id' in t]
                    additional_spotify_id = get_first(chunk, lambda m: m[0] in song_foreign_ids)
                    if additional_spotify_id is not None:
                        additional_spotify_id = additional_spotify_id[1]
                if additional_spotify_id is not None:
                    # get db_a by spotify id
                    db_a = db_get_artist_by_spotify_id(additional_spotify_id)
                if db_a is None:
                    db_a = db_update_artist(artist, genres_name, additional_spotify_id=additional_spotify_id)
                    db.session.commit()
                    new_artists.append(db_a)
            # write song
            if db_a is not None:
                # todo: we may allow artists without spotify reference so we can process more songs
                genre_id = db_a.Genres[0].GenreId if db_a.Genres is not None and len(db_a.Genres) > 0 else None
                db_s = db_update_song(song, db_a.ArtistId, genre_id, song_type=song_type,
                                      processed_songs=processed_songs)
                if db_s is not None:  # duplicate songs and songs without spotify reference are skipped
                    db_songs.append(db_s)
                    db.session.commit()

    newly_indexed_songs = db_get_song_ids_for_tracks_by_spotify_ids([m[0] for m in check_mappings])
    indexed_songs.update(newly_indexed_songs)
    not_found = [mapping for mapping in check_mappings if mapping[0] not in newly_indexed_songs]
    return db_songs, indexed_songs, not_found, new_artists, len(check_mappings) - len(not_found)


def transfer_songs_with_retry(track_mappings, genres_name, song_type=None, force_update=False):
    # echo nest api will not return all songs requested - it is not deterministic and it will never be fixed!
    processed_songs = []
    new_artists = []
    not_found = track_mappings
    found_songs = {}
    while True:
        songs, found, not_found, artists, new_tracks_count = transfer_songs(not_found, genres_name,
                                                                            song_type=song_type,
                                                                            force_update=force_update)
        processed_songs.extend(songs)
        found_songs.update(found)
        new_artists.extend(artists)
        if new_tracks_count == 0:
            break
    return processed_songs, found_songs, not_found, new_artists


def transfer_artist(spotify_id, genres_name, force_update=False):
    if not force_update:
        # check if artist exists
        db_a = db_get_artist_by_spotify_id(spotify_id)
        if db_a is not None:
            return db_a, False
    # get artist from echonest and update in db
    artist = echonest_helper.get_artist(spotify_id)
    if artist is None:
        print('spotify artist %s does not exist in echonest' % spotify_id)
        return None, False
    db_a = db_update_artist(artist, genres_name, additional_spotify_id=spotify_id)
    db.session.commit()
    return db_a, True


def transfer_similar_artists(user, root_db_a, genres_name):
    similar_artists = OrderedSet()
    sp_similar_artists = spotify_helper.get_similar_artists(user, root_db_a.SpotifyId)
    if sp_similar_artists is None:
        print('Artist id %s not found in Spotify(similar) anymore' % root_db_a.SpotifyId)
        db_mark_artist_spotify_not_found(root_db_a.ArtistId)
        db.session.commit()
        return None
    else:
        for sp_artist in sp_similar_artists['artists']:
            db_a, _ = transfer_artist(sp_artist['uri'], genres_name)
            if db_a is not None:
                db.session.commit()
                similar_artists.add(db_a.ArtistId)
    db_update_similar_artists(root_db_a.ArtistId, similar_artists, overwrite=True)
    db.session.commit()
    return similar_artists


def infer_artist_genre(similar_ids, artists_genres):
    related_genres = {}
    artists_with_genres = 0
    for similar_id in similar_ids:
        if similar_id in artists_genres:
            artists_with_genres += 1
            rgs = artists_genres[similar_id]
            for gid in rgs:
                if gid not in related_genres:
                    related_genres[gid] = 1
                else:
                    related_genres[gid] += 1
        # if artists_with_genres == 10:
        #    break
    if len(related_genres) == 0:
        return []
    # max 3, must be >= 0.5 of the biggest
    top_genres = sorted([(key, value) for key, value in related_genres.items()], key=itemgetter(1), reverse=True)[:3]
    max_count = top_genres[0][1]
    cutoff_count = math.ceil(max_count / 2.0)
    # filter(lambda x: x[1] >= cutoff_count, top_genres)
    return [(k, max_count - v) for k,v in top_genres if v >= cutoff_count]


def infer_and_store_genres_for_artist(artist_id, similar_ids, artists_genres):
    infered_genres = infer_artist_genre(similar_ids, artists_genres)
    # write infered genres
    db_update_artist_genres(artist_id, infered_genres, GenreSourceType.infered.value, update_songs=True)
    db.session.commit()
    return infered_genres


def infer_and_store_genres_for_artists(user, db_artists, genres_name):
    new_genres = {}
    for db_a in db_artists:
        # infer genres if not present in new artist
        if not db_a.Genres:
            similar_ids = transfer_similar_artists(user, db_a, genres_name)
            # infer genres
            if similar_ids:
                artists_genres = db_get_genres_for_artists(similar_ids)
                infered_genres = infer_and_store_genres_for_artist(db_a.ArtistId, similar_ids, artists_genres)
                if infered_genres:
                    new_genres[db_a.ArtistId] = infered_genres
    return new_genres


def update_genres_from_echonest():
    # get all genres
    _, genres_name = db_get_genres()
    print('got %i existing genres from database' % len(genres_name))
    genres = echonest_helper.get_all_genres()
    # write unknown genres to db
    new_genres = 0
    for g in genres['genres']:
        if g['name'] not in genres_name:
            db_g = Genre(Name=g['name'])
            db.session.add(db_g)
            new_genres += 1
    db.session.commit()
    return new_genres


def prepare_playable_tracks(user, song_ids):
    possible_tracks = db_get_spotify_track_ids_for_songs(song_ids).items()
    ordered_mappings = []
    for song_id in song_ids:
        # add mappings in order found in song_ids list
        ordered_mappings.extend([mapping for mapping in possible_tracks if mapping[1] == song_id])
    # go through spotify and return only playable tracks
    return spotify_helper.resolve_tracks_for_user(user, ordered_mappings)


def normalized_song_dedup_name(artist_id, song_name):
    return '%i_%s' % (artist_id, ci_s_normalize(song_name))
