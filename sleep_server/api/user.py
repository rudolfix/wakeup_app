import pickle
from api.exceptions import *
from api import app
from datetime import datetime
from common.user_base import UserBase
import cryptoparams


class User(UserBase):
    version = 1

    def __init__(self, sp_id):
        super().__init__(sp_id)
        self.is_new = True
        self.playlists = []
        self.created_at = datetime.utcnow()
        self.updated_at = None
        self.is_playlists_ready = False

    @staticmethod
    def upgrade_user(user):
        pass

    @staticmethod
    def serialize(user, file):
        user._version = User.version
        pickle.dump(user, file, protocol=0) # save in ASCII protocol

    @staticmethod
    def deserialize(file):
        user = pickle.load(file)
        User.upgrade_user(user)
        if user._version != User.version:
            raise UserRecordVersionMismatch(user._version, User.version)
        user.is_new = False
        return user

    @property
    def authorization_string(self):
        return User.encrypt_user_secret(self.spotify_id) + ' ' + self.spotify_access_token

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
