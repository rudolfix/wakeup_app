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
