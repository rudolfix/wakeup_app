from functools import wraps

from flask import request, redirect, url_for, make_response, render_template

from api import app
from api import user_helper
from common import spotify_helper


def spotify_authorized(f):
    @wraps(f)
    def _wrap(*args, **kwargs):
        if app.config['ADMIN_AUTH_COOKIE'] not in request.cookies:
            return redirect(url_for('login'))  # go to login page

        return f(*args, **kwargs)

    return _wrap


def check_user(f):
    @wraps(f)
    def _wrap(*args, **kwargs):
        user = user_helper.check_user(request.cookies.get(app.config['ADMIN_AUTH_COOKIE']))
        return f(user, *args, **kwargs)

    return _wrap


def render_login_error(error_title, status_code, token_data):
    return render_template('admin_login_error.html', error_title=error_title, status_code=status_code,
                           more_info=token_data)


@app.route('/admin')
def login():
    # if auth cookie does not exist redirect to spotify login
    if app.config['ADMIN_AUTH_COOKIE'] not in request.cookies:
        url = spotify_helper.spotify_login(url_for('login_completed', _external=True))
        resp = redirect(url)
    else:
        resp = redirect(url_for('dashboard'))

    return resp


@app.route('/admin/login_completed')
def login_completed():
    # check status
    if 'error' not in request.values:
        token_data, status_code = spotify_helper.token_for_code(request.values.get('code'),
                                                                url_for('login_completed', _external=True))
        if status_code == 200:
            user = user_helper.create_user(token_data)
            # now you may store cookie
            resp = make_response(redirect(url_for('dashboard')))
            resp.set_cookie(app.config['ADMIN_AUTH_COOKIE'], user.authorization_string,
                            max_age=int(token_data['expires_in']), path='/admin')
            return resp
        return render_login_error('Code exchange error', 'HTTP ' + str(status_code), token_data)
    # login error
    return render_login_error('Login error', request.values.get('error'), '')


@app.route('/admin/dashboard')
@spotify_authorized
@check_user
def dashboard(user):
    return render_template('admin_dashboard.html', authorization_header=user.authorization_string,
                           refresh_token=user.spotify_refresh_token, access_token=user.spotify_access_token)
