import os

from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config.from_object('server.config.Config')
if os.environ.get('WAKEUPP_APP_CONFIG_FILE') is not None:
    app.config.from_envvar('WAKEUPP_APP_CONFIG_FILE')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)