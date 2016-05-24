class ApiException(Exception):
    def __init__(self, status_code, msg):
        self.status_code = status_code
        super().__init__(msg)


class SpotifyApiInvalidToken(ApiException):
    def __init__(self, code, msg):
        super().__init__(401, 'Invalid Spotify access token [%s] [%s]' % (code, msg))


class SpotifyApiTokenExpired(ApiException):
    def __init__(self, code, msg):
        super().__init__(401, 'Expired Spotify access token [%s] [%s]' % (code, msg))


class SpotifyApiObjectNotFoundException(ApiException):
    def __init__(self, code, msg):
        super().__init__(404, 'Spotify object not found [%s] [%s]' % (code, msg))


class LibraryNotExistsException(ApiException):
    def __init__(self, user_id):
        super().__init__(404, 'Library for user %s does not exists' % user_id)


class LibraryNotResolvedException(ApiException):
    def __init__(self, user_id):
        super().__init__(428, 'Library for user %s still not resolved' % user_id)


class MusicGraphServerException(ApiException):
    def __init__(self, msg):
        super().__init__(500, msg)


class MusicGraphNetworkException(ApiException):
    def __init__(self, msg):
        super().__init__(500, msg)
