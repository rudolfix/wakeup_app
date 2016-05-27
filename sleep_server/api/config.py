from common.config import ConfigBase
import logging


class Config(ConfigBase):
    ENCRYPTION_IV = '2d04dd0c8d0245c58db445ab24eb8df1'
    ENCRYPTION_KEY = '62b62c1bf34ea7b996cea01662cece92'
    CLIENT_CALLBACK_URL = 'luxury8wakeup://spotifylogincallback'
    ADMIN_AUTH_COOKIE = 'spotify-auth'
    HOST_NAME = 'dev.wakeupapp.com'
    USER_STORAGE_URI = '/home/vagrant/user_storage/'
    TESTING = False
    MAXIMUM_PLAYLIST_LENGTH = 80*60*1000
    MINIMUM_PLAYLIST_LENGTH = 15*60*1000
    DEFAULT_PLAYLIST_LENGTH = 30*60*1000
    LOG_FILE = '/var/log/sleep_server/api.log'
    LOG_LEVEL = logging.DEBUG
    DEBUG = True


class TestConfig(Config):
    TEST_SPOTIFY_ID = 'rudolfix-us'
    TEST_REFRESH_TOKEN = 'AQBz4V96VzESfrk7NM0QGocj-2mNKfaIX-rAXa-ClZBbhAzkzX0xRYs07y6BFdOWK6Q1ak-5gx-FE1Q1BzoxFy3zupqQMGxlnIHUQt4qed8eY5oRyVqKB3zqx4A6bgzypf0' # put valid refresh token here. use /admin to obtain it
    TESTING = True
