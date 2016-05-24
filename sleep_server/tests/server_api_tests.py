from functools import wraps
import os, inspect
currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
os.sys.path.insert(0, parentdir)

from common import music_graph_client as mgc
from common.user_base import UserBase


def apitest(f):
    @wraps(f)
    def _wrap(*args, **kwargs):
        try:
            print(f)
            v = f(*args, **kwargs)
            if v is not None:
                print(v)
        except Exception as exc:
            print(str(type(exc)) + ':' + str(exc))
    return _wrap


user = UserBase.from_file('test_accounts/rudolfix-us.json')
user_unk = UserBase.from_file('test_accounts/rudolfix-us.json')
user_unk.spotify_id = 'unk'
apitest(mgc.get_library)(user)
apitest(mgc.get_library)(user_unk)
apitest(mgc.get_possible_playlists)(user)
apitest(mgc.get_possible_playlists)(user, 'fall_asleep')
apitest(mgc.create_playlist)(user, 'fall_asleep', 60*60*1000,828)