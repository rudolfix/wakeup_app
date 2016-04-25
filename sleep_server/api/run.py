import inspect
import os

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
os.sys.path.insert(0,parentdir)
from api import app

if __name__ == '__main__':
    app.run(app.config['HOST_NAME'], debug=app.config['DEBUG'])
