from api import app
from spotify import spotify_helper
from flask import request, redirect, url_for, make_response, render_template
import urllib.parse
from functools import wraps
from api.user import User
from api import user_helper


def spotify_authorized(f):
    @wraps(f)
    def _wrap(*args, **kwargs):
        if app.config['ADMIN_AUTH_COOKIE'] not in request.cookies:
            return redirect(url_for('login'))  # go to login page

        return f(*args, **kwargs)

    return _wrap


def render_login_error(error_title, status_code, token_data):
    return render_template('admin_login_error.html', error_title=error_title, status_code=status_code,
                           more_info=token_data)


@app.route('/admin')
def login():
    # if auth cookie does not exist redirect to spotify login
    if app.config['ADMIN_AUTH_COOKIE'] not in request.cookies:
        params = {'client_id': app.config['CLIENT_ID'],
                  'response_type': 'code',
                  'redirect_uri': url_for('login_completed', _external=True),
                  'scope': app.config['ADMIN_SPOTIFY_LOGIN_SCOPE']}
        url = app.config['SPOTIFY_ACCOUNTS_ENDPOINT'] + '/authorize?' + urllib.parse.urlencode(params)
        resp = redirect(url)
    else:
        resp = redirect(url_for('dashboard'))

    return resp


@app.route('/admin/login_completed')
def login_completed():
    # check status
    if 'error' not in request.args:
        token_data, status_code = spotify_helper.token_for_code(request.args.get('code'),
                                                                url_for('login_completed', _external=True))
        if status_code == 200:
            user = user_helper.create_user(token_data)
            # now you may store cookie
            resp = make_response(redirect(url_for('dashboard')))
            resp.set_cookie(app.config['ADMIN_AUTH_COOKIE'], user.access_cookie,
                            max_age=int(token_data['expires_in']), path='/admin')
            return resp
        return render_login_error('Code exchange error', 'HTTP ' + str(status_code), token_data)
    # login error
    return render_login_error('Login error', request.args.get('error'), '')


@app.route('/admin/dashboard')
@spotify_authorized
def dashboard():
    return render_template('admin_dashboard.html')
