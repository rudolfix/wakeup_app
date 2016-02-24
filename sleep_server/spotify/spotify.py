from api import app
from flask import request, json
from spotify import spotify_helper
from api import user_helper
from api.user import User


@app.route('/swap', methods=['POST', 'GET'])
def swap():
    auth_code = request.args.get('code')
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
    spotify_id = User.decrypt_user_secret(request.args.get['refresh_token'])
    # user must exist
    user = user_helper.load_user(spotify_id)
    if user.is_new:
        raise user_helper.UserDoesNotExist(request.args.get['refresh_token'])
    # follow user procedure in SWAP
    content, status_code = spotify_helper.refresh_token(user.spotify_refresh_token)
    if status_code == 200:
        # save new access token
        # todo: check and and parse content returned during refresh token -> set user record correctly
        user.spotify_access_token = content.access_token
        user.spotify_token_expiration = content.access_token_expiration
        user_helper.save_user(user)
    return content, status_code
