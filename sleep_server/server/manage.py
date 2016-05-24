import inspect
import os
from flask.ext.script import Manager
from flask.ext.migrate import Migrate, MigrateCommand

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
os.sys.path.insert(0,parentdir)
from server import app, db, cache
from server.models import *

migrate = Migrate(app, db)
manager = Manager(app)

manager.add_command('db', MigrateCommand)
manager.add_command('cache', cache.CacheCommand)


if __name__ == '__main__':
    manager.run()