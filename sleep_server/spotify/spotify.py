from api import app
from flask import request, json, redirect, url_for
from spotify import spotify_helper
from api import user_helper
from api.user import User


@app.route('/swap', methods=['POST', 'GET'])
def swap():
    auth_code = request.args.get('code')
    if app.config['TESTING']:
        token_data, status_code = spotify_helper.fake_token_for_code(auth_code, app.config['CLIENT_CALLBACK_URL'])
    else:
        token_data, status_code = spotify_helper.token_for_code(auth_code, app.config['CLIENT_CALLBACK_URL'])
    if status_code == 200:
        user = user_helper.create_user(token_data)
        # refresh token will contain encrypted spotify id
        # todo: designs a better auth system with independent user id. spotify user id allows to recover user record after
        # todo: app is reinstalled or user is logged again
        token_data['refresh_token'] = User.encrypt_user_secret(user.spotify_id)
    return json.jsonify(token_data), status_code


@app.route('/refresh', methods=['POST', 'GET'])
def refresh():
    # descrypt refresh token, it will contain spotify_id (currently)
    encrypted_rf = request.args.get('refresh_token')
    spotify_id = User.decrypt_user_secret(encrypted_rf)
    # user must exist
    user = user_helper.load_user(spotify_id)
    if user.is_new:
        raise user_helper.UserDoesNotExist(request.args.get['refresh_token'])
    # follow user procedure in SWAP
    token_data, status_code = spotify_helper.refresh_token(user.spotify_refresh_token)
    if status_code == 200:
        # save new access token
        user.spotify_access_token = token_data['access_token']
        user.spotify_token_expiration = token_data['expires_in']
        user_helper.save_user(user)
    return json.jsonify(token_data), status_code
