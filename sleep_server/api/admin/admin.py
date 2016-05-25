from functools import wraps
from datetime import datetime

from flask import request, redirect, url_for, make_response, render_template, Blueprint

from api import app
from api import user_helper
from common import spotify_helper, music_graph_client as mgc, common
from common.exceptions import LibraryNotExistsException, LibraryNotResolvedException

admin_bp = Blueprint('admin', __name__, template_folder='templates')


def spotify_authorized(f):
    @wraps(f)
    def _wrap(*args, **kwargs):
        if app.config['ADMIN_AUTH_COOKIE'] not in request.cookies:
            return redirect(url_for('admin.login'))  # go to login page

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


@admin_bp.route('/login')
def login():
    # if auth cookie does not exist redirect to spotify login
    if app.config['ADMIN_AUTH_COOKIE'] not in request.cookies:
        url = spotify_helper.spotify_login(url_for('admin.login_completed', _external=True))
        resp = redirect(url)
    else:
        resp = redirect(url_for('admin.dashboard'))

    return resp


@admin_bp.route('/login_completed')
def login_completed():
    # check status
    if 'error' not in request.values:
        token_data, status_code = spotify_helper.token_for_code(request.values.get('code'),
                                                                url_for('admin.login_completed', _external=True))
        if status_code == 200:
            user = user_helper.create_user(token_data)
            # now you may store cookie
            resp = make_response(redirect(url_for('admin.dashboard')))
            resp.set_cookie(app.config['ADMIN_AUTH_COOKIE'], user.authorization_string,
                            max_age=int(token_data['expires_in']), path='/admin')
            return resp
        return render_login_error('Code exchange error', 'HTTP ' + str(status_code), token_data)
    # login error
    return render_login_error('Login error', request.values.get('error'), '')


@admin_bp.route('/dashboard')
@spotify_authorized
@check_user
def dashboard(user):
    # get library status
    lib_status = None
    try:
        lib_status = mgc.get_library(user)
    except LibraryNotExistsException as nex:
        pass
    possible_playlists = None
    if lib_status is not None:
        # get age from timestamps
        now = datetime.utcnow()
        lib_status['created_ago'] = (now - lib_status['created_at']).days
        if lib_status['resolved_at'] is not None:
            lib_status['resolved_ago'] = (now - lib_status['resolved_at']).days
        if lib_status['is_resolved']:
            # get possible playlists
            possible_playlists = mgc.get_possible_playlists(user)
    # make user playlists into dict
    user_playlists = {}
    for pl in user.playlists:
        user_playlists[pl['type']] = pl.copy()
        user_playlists[pl['type']]['name'] = common.predefined_playlists[pl['type']]
    return render_template('admin_dashboard.html', user=user, lib_status=lib_status,
                           possible_playlists=possible_playlists, user_playlists=user_playlists)


@admin_bp.route('/actions', methods=['POST'])
@spotify_authorized
@check_user
def actions(user):
    action = request.values.get('action').split(':')
    if action[0] == 'resolve':
        mgc.resolve_library(user)
    elif action[0] == 'fall_asleep_auto':
        fall_asleep_dl = int(request.values.get('fall_asleep_dl')) * 60 * 1000
        user_helper.create_user_playlist(user, 'fall_asleep', fall_asleep_dl)
        user_helper.save_user(user)
    elif action[0] == 'fall_asleep':
        fall_asleep_dl = int(request.values.get('fall_asleep_dl')) * 60 * 1000
        user_helper.create_user_playlist(user, 'fall_asleep', fall_asleep_dl, int(action[1]))
        user_helper.save_user(user)
    elif action[0] == 'wake_up_auto':
        wake_up_dl = int(request.values.get('wake_up_dl')) * 60 * 1000
        user_helper.create_user_playlist(user, 'wake_up', wake_up_dl)
        user_helper.save_user(user)
    elif action[0] == 'wake_up':
        wake_up_dl = int(request.values.get('wake_up_dl')) * 60 * 1000
        user_helper.create_user_playlist(user, 'wake_up', wake_up_dl, int(action[1]))
        user_helper.save_user(user)

    return redirect(url_for('admin.dashboard'))


@admin_bp.errorhandler(Exception)
def handle_error(e):
    return app.handle_exception(e)
