from api import app
from flask import request, json
from spotify import spotify_helper


@app.route('/swap', methods=['POST', 'GET'])
def swap():
    auth_code = request.args.get('code')
    token_data, status_code = spotify_helper.token_for_code(auth_code, app.config['CLIENT_CALLBACK_URL'])
    return json.jsonify(token_data), status_code


@app.route('/refresh', methods=['POST', 'GET'])
def refresh():
    content, status_code = spotify_helper.refresh_token(request.args.get['refresh_token'])
    return content, status_code