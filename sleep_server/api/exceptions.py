from common.exceptions import ApiException


class PlaylistsDataNotReadyException(ApiException):
    def __init__(self):
        super().__init__(428, 'Playlists data still not processed')


class PlaylistIncorrectDesiredLength(ApiException):
    def __init__(self, actual_length, min_length, max_length):
        super().__init__(400, 'Playlists length can be from %i to %i, actual value is %i' %
                                           (min_length, max_length, actual_length))


class PlaylistIncorrectType(ApiException):
    def __init__(self, actual_type, possible_types):
        super().__init__(400, 'Incorrect playlist type, possible values %s, actual value %s' %
                                           (actual_type, possible_types))


class PlaylistsPropsNotSetException(ApiException):
    def __init__(self):
        super().__init__(404, 'You should set playlist properties before obtaining them')


class UserRecordVersionMismatch(ApiException):
    def __init__(self, found_ver, current_ver):
        super().__init__(500, 'Found user record ver %i but current ver is %i and no upgrade path specified'
                                           % (found_ver, current_ver))


class UserCannotDescryptSecret(ApiException):
    def __init__(self):
        super().__init__(401, 'User secret could not be descrypted')


class UserDoesNotExist(ApiException):
    def __init__(self, user_id):
        super().__init__(401, 'User with user id %s does not exist' % user_id)


class SpotifyFreeUserNotSupported(ApiException):
    def __init__(self, username):
        super().__init__(403, 'Free Spotify users are not supported [%s]' % username)


# class SpotifyApiCannotSwapToken(ApiException):
#     def __init__(self, code, msg):
#         super(ApiException, self).__init__('Expired Spotify access token [%s] [%s]' % (code, msg))
