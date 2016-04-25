import base64


class ConfigBase:
    SPOTIFY_CLIENT_ID = '3547ee3842f24500aded0f5a0afe11a5'
    SPOTIFY_CLIENT_SECRET = '9a97bf95ce2048c2a3df751a50367060'
    SPOTIFY_ACCOUNTS_ENDPOINT = 'https://accounts.spotify.com'
    SPOTIFY_LOGIN_SCOPE = 'playlist-read-private playlist-read-collaborative playlist-modify-private user-follow-read user-library-read user-read-private user-top-read'
    AUTH_HEADER = 'Basic ' + str(base64.standard_b64encode((SPOTIFY_CLIENT_ID + ':' + SPOTIFY_CLIENT_SECRET).encode('ascii')), 'ascii')
