import uuid
import pickle
from api import app
from api.exceptions import *
from datetime import datetime, timezone, timedelta
import cryptoparams


class User:
    version = 1 # class variable they say

    def __init__(self, sp_id):
        # define all instance variables
        self.is_new = True
        self.spotify_id = sp_id
        self.spotify_access_token = None
        self.spotify_refresh_token = None
        self.user_id = uuid.uuid4().hex # always generate
        self.playlists = []
        self._spotify_token_expiration = None
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = None
        self.is_playlists_ready = False

    # @classmethod
    # def from_sp__token_data(self, sp_id, sp_token, sp_encrypted_refresh_token, ap_token_expiration_seconds):
    #    pass
    @property
    def spotify_token_expiration(self):
        return self._spotify_token_expiration

    @spotify_token_expiration.setter
    def spotify_token_expiration(self, value_seconds):
        now = datetime.now(timezone.utc)
        self._spotify_token_expiration = (now + timedelta(seconds=value_seconds))

    @property
    def authorization_string(self):
        return User.encrypt_user_secret(self.spotify_id) + ' ' + self.spotify_access_token

    #@staticmethod
    #def as_user(dct):
    #    if '__user__' in dct:

    @staticmethod
    def serialize(user, file):
        user._version = User.version
        pickle.dump(user, file, protocol=0) # save in ASCII protocol

    @staticmethod
    def deserialize(file):
        user = pickle.load(file)
        if user._version != User.version:
            raise UserRecordVersionMismatch(user._version, User.version)
        user.is_new = False
        return user

    @staticmethod
    def decrypt_user_secret(secret):
        cp = cryptoparams.CryptoParams(app.config['ENCRYPTION_KEY'], app.config['ENCRYPTION_IV'])
        try:
            return cp.decrypt(secret)
        except ValueError:
            raise UserCannotDescryptSecret()

    @staticmethod
    def encrypt_user_secret(secret):
        cp = cryptoparams.CryptoParams(app.config['ENCRYPTION_KEY'], app.config['ENCRYPTION_IV'])
        return cp.encrypt(secret)

