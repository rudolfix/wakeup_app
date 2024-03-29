import os
import time
from contextlib import contextmanager

import pytest
from flask import url_for, appcontext_pushed, json

import api
from api import user_helper
from common import spotify_helper, music_graph_client as mgc, common as c


@contextmanager
def context_set(a):
    def handler(sender, **kwargs):
        pass
    with appcontext_pushed.connected_to(handler, a):
        yield


@pytest.fixture
def client():
    # api.app.config.from_object('api.config.TestConfig')
    # if os.environ.get('WAKEUPP_APP_CONFIG_FILE') is not None:
    #        api.app.config.from_envvar('WAKEUPP_APP_CONFIG_FILE')
    return api.app.test_client()


def setup_user():
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
    client = api.app.test_client()
    rv = client.get('/swap?code=0')
    assert rv.status_code == 200
    j = json.loads(rv.data)
    assert 'refresh_token' in j
    assert 'access_token' in j

    # save spotify id for later use
    sp_record = spotify_helper.get_current_user_by_token(j['access_token'])
    api.app.config["TEST_SPOTIFY_ID"] = sp_record['id']
    user = user_helper.load_user(sp_record['id'])
    api.app.config["TEST_AUTH_HEADER"] = user.authorization_string


def setup_module(module):
    with api.app.app_context():
        api.app.config.from_object('api.config.TestConfig')
        if os.environ.get('WAKEUPP_APP_CONFIG_FILE') is not None:
            api.app.config.from_envvar('WAKEUPP_APP_CONFIG_FILE')
        api.app.config['USER_STORAGE_URI'] += '../test_user_storage/'
        user_helper.init_user_storage()
        api.app.config['SERVER_NAME'] = 'dev.wakeupapp.com'
        api.app.config['DEBUG'] = True
        api.app.config['TESTING'] = True
        # delete library of the test user
        mgc.delete_library(api.app.config["TEST_SPOTIFY_ID"])
        # will start creating library etc
        setup_user()


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
    # user = user_helper.load_user(api.app.config["TEST_SPOTIFY_ID"])
    # wait for user library to be ready
    for _ in range(10):
        rv = client.get('/me/playlists', headers = headers)
        if rv.status_code == 200:
            break
        time.sleep(6)
    assert rv.status_code == 200, 'Default playlist data should be returned'
    _check_playlist_body(rv.data)
    rv = client.get('/me/playlists', headers = headers)
    assert rv.status_code == 200, 'Default playlist data should be returned'
    _check_playlist_body(rv.data)
    # skip auth headers -> should throw not authorized
    rv = client.post('/me/playlists/wake_up?desired_length=35')
    assert rv.status_code == 401
    _check_error_response_body(rv.data)
    #set playlist data
    rv = client.post('/me/playlists/wake_up?desired_length=' + str(45*60*1000), headers=headers)
    assert rv.status_code == 200
    _check_ok_response_body(rv.data)
    rv = client.get('/me/playlists', headers = headers)
    assert rv.status_code == 200, 'playlist data should be returned'
    _check_playlist_body(rv.data)
    rv = client.post('/me/playlists/fall_asleep?desired_length=' + str(35*60*1000), headers=headers)
    assert rv.status_code == 200
    _check_ok_response_body(rv.data)
    rv = client.get('/me/playlists', headers = headers)
    assert rv.status_code == 200
    _check_playlist_body(rv.data)
    #test list overwrite
    rv = client.post('/me/playlists/wake_up?desired_length=' + str(80*60*1000), headers=headers)
    assert rv.status_code == 200
    _check_ok_response_body(rv.data)
    rv = client.post('/me/playlists/wake_up?desired_length=' + str(8000*60*1000), headers=headers)
    assert rv.status_code == 400
    _check_error_response_body(rv.data)
    rv = client.post('/me/playlists/wake_up', headers=headers)
    assert rv.status_code == 400
    _check_error_response_body(rv.data)
    rv = client.get('/me/playlists', headers = headers)
    assert rv.status_code == 200
    _check_playlist_body(rv.data)


def _check_playlist_body(body):
    # should have two playlists
    j = _check_ok_response_body(body)
    assert len(j['result']) == 2, 'response should contain two playlists'
    for pl in j['result']:
        assert pl['type'] in c.possible_list_types
        assert pl['uri'] is not None, pl['type'] + ' playlist should have uri attr set'


def _check_ok_response_body(body):
    j = json.loads(body)
    # assert 'result' in j
    if not 'result' in j:
        pytest.fail('"result" dictionary key expected in OK response')
    return j


def _check_error_response_body(body):
    j = json.loads(body)
    if not 'error' in j:
        pytest.fail('"error" dictionary key expected in error response')
    err = j['error']
    req_elements = ['code', 'message', 'status']
    for el in req_elements:
        if not el in err:
            pytest.fail('"error" must contain element %s' % el)
    return err