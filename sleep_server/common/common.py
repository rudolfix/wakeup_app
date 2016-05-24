from datetime import datetime
import re as regex
import unicodedata


possible_list_types = ['wake_up', 'fall_asleep']
predefined_playlists = {'wake_up': '*Sleep App - Wake Up*', 'fall_asleep': '*Sleep App - Fall Asleep*'}


def parse_iso8601date(s):
    return datetime.strptime(s, '%Y-%m-%dT%H:%M:%SZ')


def parse_iso8601datemili(s):
    return datetime.strptime(s, '%Y-%m-%dT%H:%M:%S.%fZ')


def ci_s_normalize(s):
    return unicodedata.normalize('NFKD', s.casefold())


def isnull(val, r):
    return val if val is not None else r


def list_chunker(l, n):
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