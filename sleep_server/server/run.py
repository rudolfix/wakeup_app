import inspect
import os

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
os.sys.path.insert(0,parentdir)
from server import app
from server import server

# init logging
server.init_logging()
# start server
try:
    server.start(start_mq=True)
except Exception as e:
    app.logger.exception(e)
    raise
if __name__ == '__main__':
    app.run('localhost', port=5001, debug=app.config['DEBUG'])
