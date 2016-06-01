import inspect
import os

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
os.sys.path.insert(0,parentdir)
from api import app

if __name__ == '__main__':
    # print('binding to %s' % app.config['HOST_NAME'])
    app.run('dev.wakeupapp.com', debug=app.config['DEBUG'])
