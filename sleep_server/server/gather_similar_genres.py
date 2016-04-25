import inspect
import os

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
os.sys.path.insert(0,parentdir)
from server import db, song_helper, echonest_helper


def update_similar_genres():
    _, genres_name = song_helper.db_get_genres()
    for gname, gid in genres_name.items():
        print('updating genre %s' % gname)
        similar_genres = echonest_helper.get_similar_genres(gname)['genres']
        song_helper.db_update_similar_genres(gid, [(genres_name[i['name']], i['similarity']) for i in similar_genres])
        db.session.commit()


if __name__ == '__main__':
    update_similar_genres()