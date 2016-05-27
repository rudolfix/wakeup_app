import os

from flask import Flask

app = Flask(__name__)

app.config.from_object('api.config.Config')
if os.environ.get('WAKEUPP_APP_CONFIG_FILE') is not None:
    app.config.from_envvar('WAKEUPP_APP_CONFIG_FILE')

import api.api as api
from api.admin import admin
app.register_blueprint(admin.admin_bp, url_prefix='/admin')
api.init_logging()