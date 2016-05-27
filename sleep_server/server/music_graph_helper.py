import numpy as np
import sklearn
from sklearn import manifold, mixture, cluster
import math
import functools
import random
import networkx as nx
from operator import itemgetter
from itertools import islice

from common.common import get_first
from server import app, song_helper
from server.exceptions import CacheEntryNotExistsException

_feature_names = ['energy', 'liveness', 'tempo', 'speechiness', 'acousticness', 'instrumentalness', 'loudness',
                  'valence', 'danceability', 'key', 'mode', 'time_signature']
_clustered_features = [0, 1, 2, 3, 4, 5, 7, 8]  # acoustic features that may be clustered

_f_genre_i = 14
_f_acoustic_i = 9  # end of the acoustic features
_f_artist_id_i = 15
_f_lib_feats_i = 16
_f_song_id_i = 13
_f_duration_id_i = 12

_is_sleep_genre_threshold = 0.47  # genres with that rate of sleepy songs are considered sleepy (sleepy cluster poss.)
_is_wakeup_genre_threshold = 0.65 # genres with that many wakeful songs may be used as wakeup
_blocked_sleep_genres = ['modern performance', 'classical christmas']
_blocked_wakeup_genres = []

_significant_genres = 4  # number of top genres for artist that will be used in user pref computations

_dist_mod_sleep = [3, 0.3, 1, 0.5, 1, 1, 1, 5]  # distance modifiers when clustering songs (dimensions get weighted)
_sound_energy_dist = [0, 4, 5, 8]  # distance measure based on energy and soft features: speechiness acousticness etc.
# _dist_mod_library = [3,0.3,1,0.5,2,2,1,3]


# global stuff created or loaded from cache
class Global:
    __slots__ = ['genres', 'genres_names', 'top_songs_f_min', 'top_songs_f_max', 'artists_genres', 'features_scaler',
                 'genre_features', 'genre_sleepiness', 'genre_wakefulness', 'G_genre_sim', 'genres_similarity']

    def __init__(self):
        self.genres = None
        self.genres_names = None
        self.top_songs_f_min = None
        self.top_songs_f_max = None
        self.artists_genres = None
        self.features_scaler = None
        self.genre_features = None
        self.genre_sleepiness = None
        self.genre_wakefulness = None
        self.G_genre_sim = None
        self.genres_similarity = None


G = Global()


def load_user_library_song_features(library):
    load_tracks = set([t['song_id'] for t in library.tracks.values() if t['song_id'] is not None])
    rows = song_helper.db_select_song_rows(song_helper.db_make_song_selector_from_list(load_tracks))
    song_features = np.zeros((len(rows), 21), dtype=np.float32)
    song_features[:, :-5] = rows
    # None maps to NaN, zero it
    song_features[np.isnan(song_features)] = 0
    # index tracks
    indexed_tracks = {}
    for track in library.tracks.values():
        if track['song_id'] is not None:
            indexed_tracks[track['song_id']] = track
    # iterate over song ids taken from db
    idx = 0
    for song_id in np.nditer(song_features[:, _f_song_id_i]):  # , op_flags=['readwrite']
        # add popularity, now - added_at(hours), user_preference, playlists (count)
        track = indexed_tracks[int(song_id)]
        song = song_features[idx]
        song[16] = track['popularity']
        td = library.resolved_at - track['added_at']  # count age from last library update
        song[17] = td.days * 24 + td.seconds / (60 * 60)
        song[18] = track['user_preference']
        song[19] = len(track['playlists'])
        song[20] = track['source']
        idx += 1

    return song_features, indexed_tracks


def _first_song_idx_with_genre(song_features, gid):
    idx = -1
    for np_artist_id in np.nditer(song_features[:, _f_artist_id_i]):
        artist_id = int(np_artist_id)
        idx += 1
        if artist_id in G.artists_genres and gid in G.artists_genres[artist_id]:
            return idx
    return idx


def load_song_features(selector):
    song_features = np.array(song_helper.db_select_song_rows(selector), dtype=np.float32)
    song_features[np.isnan(song_features)] = 0
    return song_features


def prepare_songs(song_features, scaler=None):
    permutation = np.random.permutation(song_features.shape[0])
    song_features = song_features[permutation, :]
    song_genres = song_features[:, _f_genre_i]
    # normalize features
    normalized_features = song_features[:, :_f_acoustic_i]
    scaler = scaler or sklearn.preprocessing.StandardScaler(copy=False).fit(normalized_features)
    scaler.transform(normalized_features)

    return song_features, song_genres, scaler


def _f_val_prc(i, f):
    return (f[i] - G.top_songs_f_min[i]) / (G.top_songs_f_max[i] - G.top_songs_f_min[i])


def _is_sleep_song(features):
    # todo: work on sleep threshold here maybe by training SVM model on very sleepy and energetic songs
    energy_val = _f_val_prc(0, features)
    return energy_val < 0.6


def _is_wakeup_song(features):
    energy_val = _f_val_prc(0, features)
    return energy_val > 0.6


def _sleepines(features):
    # low energy(0), tempo(2), valence(7), danceability(8), loudness(6)
    # high acousticness(4)

    return 1 - _f_val_prc(0, features) + 1 - _f_val_prc(2, features) + 1 - _f_val_prc(8, features)


def _wakefulness(features):
    # low energy(0), tempo(2), valence(7), danceability(8), loudness(6)
    # high acousticness(4)
    energy = _f_val_prc(0, features)
    danceability = _f_val_prc(8, features)
    valence = _f_val_prc(7, features)
    return max(energy + valence, danceability + valence)


def _lib_song_preference(lib_song, time_score_base, time_score_days_base):
    # get a score for source (library is better), be on playlist, be recently listened to and age where
    # you score 1 point for 1-3 days and they it goes down to zero at 20th day
    # 17 - age, 18 - user_preference, 19 no of playlists, 20 source
    time_score = 0 if lib_song[17] > time_score_days_base*24 else time_score_base \
        if lib_song[17] < 3*24 else time_score_base*lib_song[17] / (time_score_days_base*24)
    # print('%i: %f' % (lib_song[17], time_score))
    source = lib_song[20]
    source_score = 0.75 if source == 3 else 0.3 if source == 1 else 0
    return time_score + source_score + lib_song[18] + lib_song[19] * 0.2


def _lib_song_sleep_preference(lib_song):
    return _lib_song_preference(lib_song, 1, 20)


def _lib_song_wake_preference(lib_song):
    return _lib_song_preference(lib_song, 3, 60)


def _k_shortest_paths(graph, source, target, k, weight=None):
    return list(islice(nx.shortest_simple_paths(graph, source, target, weight=weight), k))


def _edges_path_iter(graph, path, data=None):
    for i in range(len(path) - 1):
        n1 = path[i]
        n2 = path[i + 1]
        if data is not None:
            yield (n1, n2, graph.edge[n1][n2][data])
        else:
            yield (n1, n2, graph.edge[n1][n2])


def _find_closest_genre(graph, gid, possible_genres):
    shortest_paths = []
    for possible_gid in possible_genres:
        try:
            for path in _k_shortest_paths(graph, gid, possible_gid, 1, weight='weight'):
                w = functools.reduce(lambda w, edge: w + edge[2], _edges_path_iter(graph, path, data='weight'), 0)
                shortest_paths.append((path, w))
        except nx.NetworkXNoPath:
            pass

    if not shortest_paths:
        return None
    return sorted(shortest_paths, key=itemgetter(1))[0][0][-1]


def _euclidean_dist(ref_song, song):
    return math.sqrt(functools.reduce(
        lambda y, x: y + (x[0] - x[1]) ** 2, zip(ref_song, song), 0))


def find_closest_song(ref_song, songs, distance_features, randlimit=5):
    # finds closest vector to ref_song among songs using feature indexes 'distance_features', euclidean distance
    def ec_dist(song):
        return math.sqrt(functools.reduce(
            lambda y, x: y + (x[0] - x[1]) ** 2, zip(ref_song[distance_features], song[distance_features]), 0))

    distances = np.apply_along_axis(ec_dist, 1, songs)
    min_dis_idx = np.argsort(distances)[:randlimit][random.randint(0, min(randlimit - 1, len(distances) - 1))]
    return min_dis_idx


def _find_closest_genre_by_acoustics(ref_genre, genre_features, distance_features):
    return find_closest_song(ref_genre, genre_features, distance_features, 1)


def _print_features(f_vec):
    for i in range(min(len(_feature_names), len(f_vec))):
        print('%s: %i%% (%f)' % (_feature_names[i], _f_val_prc(i, f_vec) * 100.0, f_vec[i]))


def _top_songs_with_affinity(song_features, limit, f_affinity, f_affinity_treshold=None):
    acoustic_features = song_features[:, :_f_acoustic_i]
    if f_affinity_treshold:
        is_aff_songs = np.apply_along_axis(f_affinity_treshold, 1, acoustic_features)
        songs_with_affinity = acoustic_features[is_aff_songs]
        # print(songs_with_affinity.shape)
    else:
        songs_with_affinity = acoustic_features
    features_affinity = np.zeros(len(songs_with_affinity), dtype=np.float32)
    for s_id, f in enumerate(songs_with_affinity):
        features_affinity[s_id] = f_affinity(f)
    features_affinity_sorted_idx = np.argsort(features_affinity)
    features_affinity_sorted_idx_rev = features_affinity_sorted_idx[::-1]
    return features_affinity_sorted_idx_rev[:limit]


def _compute_genres_for_songs(lib_song_features, followed_artists, genres_affinity, f_lib_song_preference,
                              affinity_threshold,
                              genre_prevalence_threshold=0.02, genre_prevalence_count_threshold=10000,
                              significant_genres=_significant_genres):
    # artists_ids = lib_song_features[:, _f_artist_id_i]
    genres_accu = []
    genres_pref = {}
    for idx in range(lib_song_features.shape[0]):
        aid = lib_song_features[idx, _f_artist_id_i]
        # sid = lib_song_features[idx, _f_song_id_i]
        pref = f_lib_song_preference(lib_song_features[idx])
        if aid in followed_artists:
            pref += 0.25
        if aid in G.artists_genres:
            gids = G.artists_genres[aid][:significant_genres]
            genres_accu.extend(gids)
            for gid in gids:
                if gid in genres_pref:
                    genres_pref[gid] += pref
                else:
                    genres_pref[gid] = pref
    genres_count = np.bincount(genres_accu)

    # lambda f: (_sleepines(f)-min_sleepiness)/(max_sleepiness-min_sleepiness)
    # genre_sleepiness = np.apply_along_axis(_sleepines, 1, genre_features)
    # genres_count_weighted = np.multiply(genres_count,genre_sleepiness[:len(genres_count)])
    tot_in_sleep = sum(genres_count[genres_affinity[:len(genres_count)] > affinity_threshold])
    # print(tot_in_sleep)
    # print(genres_count_weighted.shape)
    top_sleep_genres = []
    g_bin_sort = np.argsort(genres_count)[::-1]
    for i in g_bin_sort:
        cnt = genres_count[i]
        prevalence = cnt / tot_in_sleep
        # mind the OR below
        if genres_affinity[i] > affinity_threshold and \
                (cnt > genre_prevalence_count_threshold or prevalence > genre_prevalence_threshold):
            top_sleep_genres.append((int(i), prevalence, genres_affinity[i], genres_pref[i]))

    return sorted(top_sleep_genres, key=itemgetter(3), reverse=True)


def get_random_song_slice_with_length(song_features, desired_length, add_margin):
    avg_length = np.mean(song_features[:, _f_duration_id_i])
    tot_songs = len(song_features)
    idx = random.randint(0, tot_songs - int(desired_length/avg_length) - 1)
    c_len = 0
    tot_len = desired_length + int(desired_length*add_margin)
    songs = []
    while True:
        s = song_features[idx]
        songs.append(s)
        c_len += s[_f_duration_id_i]
        if c_len > tot_len:
            break
        idx = (idx + 1) % tot_songs

    return songs, c_len


def trim_song_slice_length(track_mappings, song_features, desired_length):
    # trims songs from the right
    tracks = []
    c_len = 0
    for track_id, song_id in track_mappings:
        song = get_first(song_features, lambda s: s[_f_song_id_i] == song_id)
        c_len += song[_f_duration_id_i]
        tracks.append(track_id)
        if c_len > desired_length:
            break
    return tracks, c_len


def trim_song_slice_length_by_acoustics(track_mappings, song_features, desired_length, distance_features):
    # trims songs by computing acoustic difference and finding most similar pairs x - o - x
    c_len = 0
    # get features of mapped tracks
    mapped_song_features = []
    mapped_song_adiffs = []
    # could not find anything better than this, maybe apply_along_axis..
    for track_id, song_id in track_mappings:
        song = get_first(song_features, lambda s: s[_f_song_id_i] == song_id)
        c_len += song[_f_duration_id_i]
        mapped_song_features.append(song)
    # create distances
    for idx in range(len(mapped_song_features)-2):
        song = mapped_song_features[idx]
        ref_song = mapped_song_features[idx+2]
        mapped_song_adiffs.append(_euclidean_dist(ref_song[distance_features], song[distance_features]))
    # print('dists %s len %i' % (mapped_song_adiffs, len(mapped_song_adiffs)))

    while True:
        # remove songs between closest neighbours, +1 to find middle element
        rem_idx = min(range(len(mapped_song_adiffs)), key=mapped_song_adiffs.__getitem__) + 1
        rem_len = mapped_song_features[rem_idx][_f_duration_id_i]
        if c_len - rem_len < desired_length:
            break;  # stay above desired_length
        c_len -= rem_len
        # del removed song
        del mapped_song_features[rem_idx]
        del track_mappings[rem_idx]
        # del from distances
        if rem_idx < len(mapped_song_adiffs):
            del mapped_song_adiffs[rem_idx]
            # update distances
            song = mapped_song_features[rem_idx-1]
            ref_song = mapped_song_features[rem_idx+1]
            mapped_song_adiffs[rem_idx-1] = _euclidean_dist(ref_song[distance_features], song[distance_features])
        else:
            del mapped_song_adiffs[rem_idx-1]
        # print('dists %s len %i' % (mapped_song_adiffs, len(mapped_song_adiffs)))

    return [t[0] for t in track_mappings], int(c_len)


def compute_sleep_genres(library_features, followed_artists, check_songs=100):
    most_n_indexer = _top_songs_with_affinity(library_features, check_songs, _sleepines)
    most_song_features = library_features[most_n_indexer]
    # print(gr_song_features.shape)
    # most_song_genres = library_genres[most_n_indexer]
    # most_features = most_song_features[:, _clustered_features]
    # most_printable_features = most_song_features[:, :_f_acoustic_i]
    genres = _compute_genres_for_songs(most_song_features, followed_artists, G.genre_sleepiness,
                                       _lib_song_sleep_preference, _is_sleep_genre_threshold)
    return [g for g in genres if G.genres[g[0]] not in _blocked_sleep_genres], most_song_features


def compute_wakeup_genres(library_features, followed_artists, check_songs=100):
    most_n_indexer = _top_songs_with_affinity(library_features, check_songs, _wakefulness)
    most_song_features = library_features[most_n_indexer]
    genres = _compute_genres_for_songs(most_song_features, followed_artists, G.genre_wakefulness,
                                       _lib_song_wake_preference, _is_wakeup_genre_threshold,
                                       significant_genres=8)
    return [g for g in genres if G.genres[g[0]] not in _blocked_wakeup_genres], most_song_features


def compute_popular_genres(library_features, followed_artists):
    # gent genre for all possible songs, genres affinity is disregarded due to 0 for affinity_threshold
    gpt = min(10/library_features.shape[0], 0.01)
    genres = _compute_genres_for_songs(library_features, followed_artists, G.genre_sleepiness,
                                       _lib_song_sleep_preference, affinity_threshold=0, genre_prevalence_threshold=gpt,
                                       genre_prevalence_count_threshold=10)
    return genres, library_features


def best_song_idx_with_genre(song_features, gid, min_duration_ms, max_duration_ms, f_affinity_threshold, randlimit):
    def best_dist(song):
        artist_id = int(song[_f_artist_id_i])
        duration_ms = int(song[_f_duration_id_i])
        if artist_id in G.artists_genres and gid in G.artists_genres[artist_id] and f_affinity_threshold(song) \
                and max_duration_ms > duration_ms > min_duration_ms:
            return _lib_song_wake_preference(song)
        else:
            return -1

    # for x in np.nditer(a, flags=['external_loop'], order='F'): but you need to transpose a
    distances = np.apply_along_axis(best_dist, 1, song_features)
    # print('best_idx choose among %i' % len(distances[distances>-1]))
    if np.all(distances == -1):
        return _first_song_idx_with_genre(song_features, gid)
    else:
        # get only != -1
        sorted_idxs = np.argsort(distances)
        sorted_idxs = sorted_idxs[distances[sorted_idxs] > -1][::-1][:randlimit]
        # r_idx = random.randint(0, min(randlimit - 1, len(distances) - 1))
        # print('choose from %s idx %i' % (sorted_idxs, r_idx))
        return random.choice(sorted_idxs)


def find_closest_nodes_subgraph(graph, source, targets):
    distances = []
    min_len = nx.number_of_nodes(graph) + 1
    for t in targets:
        try:
            l = len(nx.dijkstra_path(graph, source, t, weight='weight'))
        except nx.NetworkXNoPath:
            l = nx.number_of_nodes(graph) + 1
        if l < min_len:
            min_len = l
        distances.append((t, l))

    return [l for l in distances if l[1] == min_len]


def generate_wakeup_playlist(wake_gid, lib_wake_song_features, gr_song_features, top_sleep_genres, top_genres,
                             desired_length, max_song_duration_ms=10*60*1000):
    wake_song_features = lib_wake_song_features[:, :_f_lib_feats_i]
    # find #start genre song and then #end genre with speechiness, acousticness and instru as close as possible
    # morph energy, temp, dance, valence linearly
    # wake_song_features has wakeful songs filtered for current user
    # find the most wakeful song of given gid
    init_song_idx = best_song_idx_with_genre(lib_wake_song_features, wake_gid, 2 * 60 * 1000, max_song_duration_ms,
                                             _is_wakeup_song, 5)
    init_song = wake_song_features[init_song_idx]
    # find matchin end genre from sleep genres by speechiness, acousticness and instru
    sound_similarity = [3, 4, 5]
    energy_similarity = [0, 2, 8]
    possible_sleep_genres = [g[0] for g in top_sleep_genres]
    # genre similarity via graph works much better
    end_gid = random.choice(find_closest_nodes_subgraph(G.G_genre_sim, wake_gid, possible_sleep_genres))[0]
    app.logger.debug('going from %s to %s' % (G.genres[end_gid], G.genres[wake_gid]))
    # print('start genre %s' % G.genres[wake_gid])
    # print('end genre %s' % G.genres[end_gid])
    from server import cache
    sleepy_clusters = cache.get_genre_clusters('sleep', end_gid)
    end_songs = random.choice(sleepy_clusters)[2][:300, :]  # np.vstack(c[2] for c in sleepy_clusters)
    end_song_idx = find_closest_song(init_song, end_songs, sound_similarity, 1)
    end_song = end_songs[end_song_idx]
    # use genre similarity graph to connect wake_gid to end_gid
    genre_path = []
    try:
        for path in _k_shortest_paths(G.G_genre_sim, wake_gid, end_gid, 1, weight='weight'):
            genre_path = path
            # print(path)
    except nx.NetworkXNoPath:
        raise  # todo: handle NetworkXNoPath somehow

    # part of replace_closest_gid closure
    possible_genres = [g[0] for g in top_genres]

    def replace_closest_gid(gid):
        # print(possible_genres)
        if gid not in possible_genres:
            c_gid = _find_closest_genre(G.G_genre_sim, gid, possible_genres)
            if c_gid is not None:
                # print('----------replaced with %s(%i)' % (G.genres[c_gid], c_gid))
                return c_gid

        return gid

    rem_length = int(desired_length - init_song[_f_duration_id_i] - end_song[_f_duration_id_i])
    # get average len
    avg_song_len = int(np.mean(G.genre_features[np.asarray(genre_path, dtype=np.int32)][:, _f_duration_id_i]))
    # get number of steps
    expected_steps = round(rem_length / avg_song_len)
    # morph song into end song in expected_steps + 1 steps (+1 -> we need to finish one step before end_song)
    song_diff = (end_song - init_song) / (expected_steps + 1)
    # var below will be morphed during iteration
    song_iter = np.copy(init_song)
    wakeup_playlist = [init_song]
    path_step = len(genre_path) / expected_steps
    # print('expected: %i path_step %f genres %i' % (expected_steps, path_step, len(genre_path)))
    for i in range(expected_steps):
        song_iter += song_diff
        path_idx = int(path_step * i + path_step/2)
        gid = genre_path[path_idx]
        # print('processing %s' % mgh.G.genres[gid])
        # choose afinity func
        if i <= expected_steps // 3:
            # f_affinity = _wakefulness
            # f_has_affinity = _is_wakeup_song
            cluster_type = 'wakeup'
            dist_index = energy_similarity
            gid = replace_closest_gid(gid)
            # c_songs = gr_song_features[gr_song_genres==gid]
            # clusters = extract_sleepy_clusters(gid, dist_mod_sleep, f_affinity, f_has_affinity, show_clusters=False)
            # c_songs = np.vstack(c[2] for c in clusters)
            # print(len(c_songs))
        elif i <= 2*expected_steps // 3:
            # f_affinity = lambda x: 1  # identity
            # f_has_affinity = lambda x: True
            cluster_type = 'pop'
            dist_index = energy_similarity
            gid = replace_closest_gid(gid)
            # c_songs = gr_song_features[gr_song_genres==gid]
            # clusters = extract_sleepy_clusters(gid, dist_mod_sleep, f_affinity, f_has_affinity, show_clusters=False)
            # c_songs = np.vstack(c[2] for c in clusters)
            # print(len(c_songs))
        else:
            # f_affinity = _sleepines
            # f_has_affinity = _is_sleep_song
            cluster_type = 'sleep'
            dist_index = _sound_energy_dist
            # find any song from cluster
            # clusters = extract_sleepy_clusters(gid, dist_mod_sleep, f_affinity, f_has_affinity, show_clusters=False)
            # c_songs = np.vstack(c[2] for c in clusters)

        # clusters = init_extract_genre_clusters(gid, _dist_mod_sleep, f_affinity, f_has_affinity)
        try:
            clusters = cache.get_genre_clusters(cluster_type, gid)
        except CacheEntryNotExistsException:
            clusters = cache.get_genre_clusters('pop', gid)
        c_songs = np.vstack(c[2] for c in clusters)
        # print(len(c_songs))
        # todo: search many closest songs and order by user preferences then choose -> known songs will pop in!
        c_song_idx = find_closest_song(song_iter, c_songs, dist_index)
        # print('%i from %s ----by %s' % (int(c_songs[c_song_idx][15]),
        #                                 f_affinity.__name__,
        #                                 song_helper.db_get_artists_name(c_songs[c_song_idx][15])))
        wakeup_playlist.append(c_songs[c_song_idx])
    wakeup_playlist.append(end_song)

    return wakeup_playlist[::-1]


def init_extract_genre_clusters(genre_id, dist_mod, f_affinity, f_has_affinity, max_duration_ms = 10*60*1000,
                                song_limit=5000, preserve_clusters_size=0.2, min_cluster_affinity_level=0):
    significant_clusters = []
    song_features = load_song_features(song_helper.db_make_song_selector_for_genre(genre_id, max_duration_ms,
                                                                                   song_limit,
                                                                                   significant_genres=_significant_genres))
    # afaik there is one empty genre
    if len(song_features) == 0:
        return significant_clusters
    song_features, _, _ = prepare_songs(song_features, G.features_scaler)
    # remove songs without affinity (sleepy, wakeful etc)
    songs_affinity = np.apply_along_axis(f_has_affinity, 1, song_features)
    song_features = song_features[songs_affinity]
    weighted_features = song_features[:, _clustered_features] * np.asarray(dist_mod)
    # get clusters
    dpgmm = mixture.DPGMM(n_components=12, covariance_type='tied', n_iter=1000, verbose=0)
    dpgmm.fit(weighted_features)
    y_pred = dpgmm.predict(weighted_features)
    print('cluster sizes: %s' % str(np.bincount(y_pred)))
    # find clusters > 30% of all elements
    cluster_sizes = np.bincount(y_pred)
    for i, c in enumerate(cluster_sizes):
        if c / len(y_pred) > preserve_clusters_size:
            significant_clusters.append([i, c])
    if len(significant_clusters) == 0:
        # add biggest cluster
        max_c_idx = np.argmax(cluster_sizes)
        significant_clusters.append([max_c_idx, cluster_sizes[max_c_idx]])
    print(significant_clusters)
    # remove outliers
    for cluster in significant_clusters:
        cluster_songs_affinity = []
        cluster_songs = []
        cluster_id = cluster[0]
        cluster_features = weighted_features[y_pred == cluster_id]
        all_cluster_features = song_features[y_pred == cluster_id]
        # this will detect and remove outliers (songs with different accoustics than the core)
        clf = sklearn.svm.OneClassSVM(nu=0.1, kernel="rbf", gamma=0.1)
        clf.fit(cluster_features)
        novelty_pred = clf.predict(cluster_features)
        print('%% of outliers in dataset: %f%%' %
              (novelty_pred[novelty_pred == -1].size * 100.0 / cluster_features.shape[0]))
        novelty_decision = clf.decision_function(cluster_features)[:, 0]
        novelty_decision_sort = np.argsort(novelty_decision)[::-1]
        for sort_id in novelty_decision_sort:
            if novelty_pred[sort_id] == 1:
                song = all_cluster_features[sort_id]
                cluster_songs_affinity.append(f_affinity(song))
                cluster_songs.append(song)
        cluster.append(np.array(cluster_songs))
        cluster.append(np.mean(cluster_songs_affinity))
    # print(significant_clusters)
    # return cluster list (cluster_id, size, songs, sleepiness)
    return [c for c in significant_clusters if c[3] > min_cluster_affinity_level]  # leave only sleepy clusters


def init_compute_genre_features(genres, song_features, song_genres):
    # compute genres average acoustic features and level of _sleepines/wakefullness defined as
    # no of song of given type/all songs in genre
    genre_features = np.zeros((len(genres) + 1, _f_duration_id_i+1), dtype=np.float32)
    genre_sleepiness = np.zeros((len(genres) + 1), dtype=np.float32)
    genre_wakefulness = np.zeros((len(genres) + 1), dtype=np.float32)
    for genre_id in genres:
        genre_songs = song_features[song_genres == genre_id][:, :_f_duration_id_i+1]
        if genre_songs.shape[0] > 0:
            genre_songs_sleepiness = np.apply_along_axis(lambda f: 1 if _is_sleep_song(f) else 0, 1, genre_songs)
            genre_songs_wakefulness = np.apply_along_axis(lambda f: 1 if _is_wakeup_song(f) else 0, 1, genre_songs)
            genre_features[genre_id] = np.mean(genre_songs, axis=0)
            genre_sleepiness[genre_id] = np.mean(genre_songs_sleepiness)
            genre_wakefulness[genre_id] = np.mean(genre_songs_wakefulness)

    return genre_features, genre_sleepiness, genre_wakefulness


def init_similar_genres_from_similar_artists(artists_genres, connected_metric_f=len, max_noise_edges=300):
    # init similarity with genre co-occurence
    genre_similarity = {}
    edge_count = 0

    def proc_l2l(g_l, s_g_l):
        edge_count = 0
        for gid in g_l:
            if gid not in genre_similarity:
                g_dict = {}
                genre_similarity[gid] = g_dict
            else:
                g_dict = genre_similarity[gid]
            for s_gid in s_g_l:
                if s_gid != gid:
                    if s_gid not in g_dict:
                        g_dict[s_gid] = 1
                    else:
                        g_dict[s_gid] += 1
                    edge_count += 1
        return edge_count

    for g_l in artists_genres.values():
        if len(g_l) == 1:
            continue
        # all genres on the list co-occur
        edge_count += proc_l2l(g_l, g_l)

    n_nodes = len(genre_similarity)
    n_pos_edges = n_nodes * (n_nodes - 1) / 2
    prob_edge = edge_count / n_pos_edges
    app.logger.debug('%i nodes, %i possible edges, %i real edges, %f prob of an edge' % (n_nodes, n_pos_edges, edge_count,
                                                                              prob_edge))
    # should be modelled as binomial dbinom(x, edge_count, 1/n_pos_edges) but with small p we use poisson
    cp = 0
    min_connections = 0
    for n_e in range(0, 15):
        # compute as long as remaining probablity allows creation <= max_noise_edges
        p = math.pow(prob_edge, n_e) * math.pow(math.e, -prob_edge) / math.factorial(n_e)
        cp += p
        noise_edges = math.ceil((1 - cp) * n_pos_edges)
        app.logger.debug('----prob of %i edges = %f, %i noise edges may be stil created' % (n_e, p, noise_edges))
        if noise_edges < max_noise_edges:
            min_connections = n_e + 1
            break
    app.logger.debug('connections below %i will be pruned' % min_connections)

    # using similar artists will never be necessary. we already have too much data from co occurence
    # if use_foreign_sim:
    #    txt = 'SELECT ArtistId, SimilarArtistId, Dist FROM SimilarArtists ORDER BY ArtistId, Dist'
    #    s = sqltext(txt)
    #    rows = db.session.execute(s).fetchall()
    #    rc = 0
    #    for row in rows:
    #        if row[0] in artists_genres and row[1] in artists_genres:
    #            proc_l2l(artists_genres[row[0]], artists_genres[row[1]])
    #        if rc % 100000 == 0:
    #            print(rc)
    #        rc += 1
    #        # rows = db.session.execute(s).fetchmany()

    # find maximally connected genre
    max_g = max([(i[0], connected_metric_f(i[1].values())) for i in genre_similarity.items()], key=itemgetter(1))
    # print(max_g)
    # print(genres[max_g[0]])
    # normalize weights
    for gid in genre_similarity:
        g_dict = genre_similarity[gid]
        for s_gid in list(g_dict.keys()):
            if g_dict[s_gid] >= min_connections:
                g_dict[s_gid] = 1 - connected_metric_f([g_dict[s_gid]]) / max_g[1]
            else:
                g_dict.pop(s_gid)

    return genre_similarity, min_connections, 1 - connected_metric_f([min_connections]) / max_g[1]


def init_compute_genre_similarity_graph(genre_similarity):
    graph = nx.Graph()
    # similar_genres = load_similar_genres() # poor and not fully connected graph
    # similar_genres = init_similar_genres_from_similar_artists(artists_genres, connected_metric_f=lambda x: math.log(sum(x))
    for gid, simgenres in genre_similarity.items():
        for simg in simgenres.items():
            graph.add_edge(gid, simg[0], weight=simg[1])
    return graph


def init_connect_genre_graph_components(graph, max_distance, genres, genres_names):
    g_comps = sorted(nx.connected_components(graph), key=len)
    # assume there are few very small disconnected components, connect them back using names ;>
    connect_via = {'j-core': 'hardcore techno', 'hip hop': 'hip hop', 'indie': 'indie rock', 'folk': 'folk',
                   'pop': 'pop',
                   'rock': 'rock',
                   'reggae': 'reggae', 'jazz': 'contemporary jazz'}
    all_nodes = list(graph.nodes())
    for comp in g_comps[:-1]:
        app.logger.debug('cliq len %i: %s' % (len(comp), comp))
        for fragment, gn in connect_via.items():
            to_connect = [c for c in comp if fragment in genres[c]]
            if to_connect:
                gn_id = genres_names[gn]
                if gn_id not in all_nodes:
                    raise nx.NetworkXNoPath()
                for tc in to_connect:
                    # print('connect %s to %s' % (genres[tc], gn))
                    graph.add_edge(gn_id, tc, weight=max_distance)
        # print('-------------')


def init_compute_sleep_clusters():
    for gid, sleepiness_lvl in enumerate(G.genre_sleepiness):
        if gid in G.genres:
            gname = G.genres[gid]
            if gname not in _blocked_sleep_genres and sleepiness_lvl > _is_sleep_genre_threshold:
                yield gid, init_extract_genre_clusters(gid, _dist_mod_sleep, _sleepines, _is_sleep_song)


def init_compute_wakeup_clusters():
    for gid, wakefulness_lvl in enumerate(G.genre_wakefulness):
        if gid in G.genres:
            gname = G.genres[gid]
            if gname not in _blocked_wakeup_genres and wakefulness_lvl > _is_wakeup_genre_threshold:
                yield gid, init_extract_genre_clusters(gid, _dist_mod_sleep, _wakefulness, _is_wakeup_song)


def init_compute_pop_clusters():
    for gid in G.genres:
        yield gid, init_extract_genre_clusters(gid, _dist_mod_sleep, _wakefulness, lambda x: True)#lambda x: 1, lambda x: True)


def init_songs_db():
    glob = Global()
    # init genres
    glob.genres, glob.genres_names = song_helper.db_get_genres()
    glob.artists_genres = song_helper.db_get_all_artists_genres()
    # init genres similarity graph
    glob.genres_similarity, _, max_dist = init_similar_genres_from_similar_artists(glob.artists_genres,
                                                                                   connected_metric_f=lambda x: sum(x))
    glob.G_genre_sim = init_compute_genre_similarity_graph(glob.genres_similarity)
    init_connect_genre_graph_components(glob.G_genre_sim, max_dist, glob.genres, glob.genres_names)

    return glob


