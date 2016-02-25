import os
import api
from api import user_helper
from spotify import spotify_helper
from flask import url_for, appcontext_pushed, json
import pytest
from contextlib import contextmanager
import requests
import urllib.parse


@contextmanager
def context_set(a):
    def handler(sender, **kwargs):
        pass
    with appcontext_pushed.connected_to(handler, a):
        yield


def setup_module(module):
    with api.app.app_context():
        api.app.config.from_object('api.config.TestConfig')
        if os.environ.get('WAKEUPP_APP_CONFIG_FILE') is not None:
            api.app.config.from_envvar('WAKEUPP_APP_CONFIG_FILE')
        api.app.config['USER_STORAGE_URI'] += '../test_user_storage/'
        user_helper.init_user_storage()
        api.app.config['SERVER_NAME'] = api.app.config['HOST_NAME']
        api.app.config['DEBUG'] = True
        api.app.config['TESTING'] = True
        # token_path = '/vagrant/' + api.app.config['TEST_REFRESH_TOKEN']
        # with open(token_path, 'r') as f:
        #    api.app.config['TEST_REFRESH_TOKEN'] = f.read().replace('\n', '')


@pytest.fixture
def client():
    # api.app.config.from_object('api.config.TestConfig')
    # if os.environ.get('WAKEUPP_APP_CONFIG_FILE') is not None:
    #        api.app.config.from_envvar('WAKEUPP_APP_CONFIG_FILE')
    return api.app.test_client()


def test_spotify_swap(client):
    with api.app.app_context():
        redirect_url = url_for('swap', _external=True)
        url = spotify_helper.spotify_login(redirect_url)
    # get spotify response
    # while True:
    #     resp = requests.get(url, allow_redirects=False)
    #     assert resp.status_code == 301, 'swap token test will only work when you allow to login seamlessly, use /admin to log in'
    #     if resp.location.startswith(redirect_url):
    #         redirected_to = resp.location
    #         break

    # use code from response
    #l = urllib.parse(redirected_to)
    #with api.app.test_request_context('/swap?code=0'):
    rv = client.get('/swap?code=0')
    assert rv.status_code == 200
    j = json.loads(rv.data)
    assert 'refresh_token' in j
    assert 'access_token' in j

    #save spotify id for later use
    sp_record = spotify_helper.get_current_user_by_token(j['access_token'])
    api.app.config["TEST_SPOTIFY_ID"] = sp_record['id']
    user = user_helper.load_user(sp_record['id'])
    api.app.config["TEST_AUTH_HEADER"] = user.authorization_string


def test_spotify_refresh(client):

    encr_rf, _ = api.app.config["TEST_AUTH_HEADER"].split(' ')
    rv = client.get('/refresh?refresh_token=' + encr_rf)
    assert rv.status_code == 200
    assert b'access_token' in rv.data
    assert b'refresh_token' not in rv.data
    # access token was updated
    user = user_helper.load_user(api.app.config["TEST_SPOTIFY_ID"])
    api.app.config["TEST_AUTH_HEADER"] = user.authorization_string


def test_create_playlist(client):
    headers = {'Authorization': api.app.config['TEST_AUTH_HEADER']}
    rv = client.get('/me/playlists', headers = headers)
    assert rv.status_code == 428, 'Playlists data expected to be generating'
    # set playlist generation flag
    user = user_helper.load_user(api.app.config["TEST_SPOTIFY_ID"])
    user.is_playlists_ready = True
    user_helper.save_user(user)
    rv = client.get('/me/playlists', headers = headers)
    assert rv.status_code == 404, 'Playlist data is not set should be returned'
    #set playlist data
    rv = client.post('/me/playlists/wake_up?desired_length=35')
    assert rv.status_code == 401
    rv = client.post('/me/playlists/wake_up?desired_length=' + str(45*60*1000), headers=headers)
    assert rv.status_code == 200
    rv = client.get('/me/playlists', headers = headers)
    assert rv.status_code == 404, 'Playlist data is not set should be returned'
    rv = client.post('/me/playlists/fall_asleep?desired_length=' + str(35*60*1000), headers=headers)
    assert rv.status_code == 200
    rv = client.get('/me/playlists', headers = headers)
    assert rv.status_code == 200
    #test list overwrite
    rv = client.post('/me/playlists/wake_up?desired_length=' + str(80*60*1000), headers=headers)
    assert rv.status_code == 200
    rv = client.post('/me/playlists/wake_up?desired_length=' + str(8000*60*1000), headers=headers)
    assert rv.status_code == 400
    rv = client.get('/me/playlists', headers = headers)
    assert rv.status_code == 200
    #check number of playlists
