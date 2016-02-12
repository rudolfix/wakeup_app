from api import app
import requests
import cryptoparams


def token_for_code(auth_code, redirect_uri):
    headers = {'Authorization': app.config['AUTH_HEADER']}
    form = {'grant_type': 'authorization_code',
            'redirect_uri': redirect_uri,
            'code': auth_code}
    resp = requests.post(app.config['SPOTIFY_ACCOUNTS_ENDPOINT'] + '/api/token', form, headers=headers)
    token_data = resp.json()
    if resp.status_code == 200:
        cp = cryptoparams.CryptoParams(app.config['ENCRYPTION_KEY'], app.config['ENCRYPTION_IV'])
        # encrypt the refresh token before forwarding to the client
        refresh_token = token_data["refresh_token"]
        token_data["refresh_token"] = cp.encrypt(refresh_token)
    #propagate response status code
    #print(str(token_data))
    resp.close()
    return token_data, resp.status_code


def refresh_token(encrypted_token):
    # Request a new access token using the POST:ed refresh token
    headers = {'Authorization': app.config['AUTH_HEADER']}
    #decrypt refresh token
    cp = cryptoparams.CryptoParams(app.config['ENCRYPTION_KEY'], app.config['ENCRYPTION_IV'])
    refresh_token = cp.decrypt(encrypted_token)
    form = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }
    resp = requests.post(app.config['SPOTIFY_ACCOUNTS_ENDPOINT'] + '/api/token', form, headers=headers)
    return resp.content, resp.status_code
