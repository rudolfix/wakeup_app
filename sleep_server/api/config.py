import base64


class Config(object):
    CLIENT_ID = '3547ee3842f24500aded0f5a0afe11a5'
    CLIENT_SECRET = '9a97bf95ce2048c2a3df751a50367060'
    ENCRYPTION_IV = '2d04dd0c8d0245c58db445ab24eb8df1'
    ENCRYPTION_KEY = '62b62c1bf34ea7b996cea01662cece92'
    CLIENT_CALLBACK_URL = 'wakeupapp://'
    AUTH_HEADER = 'Basic ' + str(base64.standard_b64encode((CLIENT_ID + ':' + CLIENT_SECRET).encode('ascii')), 'ascii')
    SPOTIFY_ACCOUNTS_ENDPOINT = 'https://accounts.spotify.com'
    SPOTIFY_LOGIN_SCOPE = 'playlist-read-private playlist-read-collaborative playlist-modify-private user-follow-read user-library-read user-read-private'
    ADMIN_AUTH_COOKIE = 'spotify-auth'
    HOST_NAME = 'dev.wakeupapp.com'
    USER_STORAGE_URI = '/home/vagrant/user_storage/'
    TESTING = False
    MOCKUP_MIN_PLAYLIST_GEN_SEC = 15
    MOCKUP_MAX_PLAYLIST_GEN_SEC = 2*60
    MAXIMUM_PLAYLIST_LENGTH = 80*60*1000
    DEBUG = True


class TestConfig(Config):
    # USER_STORAGE_URI = super.USER_STORAGE_URI + '/../test_user_storage/'
    TEST_REFRESH_TOKEN = 'AQBz4V96VzESfrk7NM0QGocj-2mNKfaIX-rAXa-ClZBbhAzkzX0xRYs07y6BFdOWK6Q1ak-5gx-FE1Q1BzoxFy3zupqQMGxlnIHUQt4qed8eY5oRyVqKB3zqx4A6bgzypf0' # put valid refresh token here. use /admin to obtain it
    TESTING = True
    MOCKUP_MIN_PLAYLIST_GEN_SEC = 10000
    MOCKUP_MAX_PLAYLIST_GEN_SEC = 10001
