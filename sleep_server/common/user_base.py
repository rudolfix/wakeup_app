import uuid
from datetime import datetime, timedelta
from flask import json


class UserBase:
    def __init__(self, sp_id):
        self.spotify_id = sp_id
        self.spotify_access_token = None
        self.spotify_refresh_token = None
        self._spotify_token_expiration = None
        self.user_id = uuid.uuid4().hex  # always generate

    @property
    def spotify_token_expiration(self):
        return self._spotify_token_expiration

    @spotify_token_expiration.setter
    def spotify_token_expiration(self, value_seconds):
        now = datetime.utcnow()
        self._spotify_token_expiration = (now + timedelta(seconds=value_seconds))

    def update_refresh_token(self, access_token, expires_in):
        # save new access token
        self.spotify_access_token = access_token
        self.spotify_token_expiration = expires_in

    def to_json(self):
        return json.dumps(self.__dict__)

    @staticmethod
    def from_json(jsons):
        u = UserBase(None)
        u.__dict__ = json.loads(jsons)
        return u

    @staticmethod
    def from_file(path):
        u = UserBase(None)
        with open(path) as f:
            u.__dict__ = json.load(f)
        return u
