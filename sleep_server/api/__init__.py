from flask import Flask

app = Flask(__name__)
app.config.from_object('api.config.Config')

import api.api
import admin.admin
import spotify.spotify