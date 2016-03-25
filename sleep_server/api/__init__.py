from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)
app.config.from_object('api.config.Config')
if os.environ.get('WAKEUPP_APP_CONFIG_FILE') is not None:
    app.config.from_envvar('WAKEUPP_APP_CONFIG_FILE')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

from api.models import Artist

import api.api
import admin.admin
import spotify.spotify