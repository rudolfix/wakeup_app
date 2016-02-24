import uuid
import pickle
from api.api import ApiException
from datetime import datetime, timezone, timedelta
import cryptoparams
from api import app


class User:
    version = 1 # class variable they say

    def __init__(self, sp_id):
        # define all instance variables
        self.is_new = True
        self.spotify_id = sp_id
        self.spotify_access_token = None
        self.spotify_refresh_token = None
        self.user_id = uuid.uuid4().hex #always generate
        self.playlists = None
        self._spotify_token_expiration = None
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = None

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
    def access_cookie(self):
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
        if(user._version != User.version):
            raise UserRecordVersionMismatch(user._version, User.version)
        user.is_new = False
        return user

    @staticmethod
    def decrypt_user_secret(secret):
        cp = cryptoparams.CryptoParams(app.config['ENCRYPTION_KEY'], app.config['ENCRYPTION_IV'])
        # todo: encapsulate encryption exception raise user_helper.UserCannotDescryptSecret()
        return cp.decrypt(secret)

    @staticmethod
    def encrypt_user_secret(secret):
        cp = cryptoparams.CryptoParams(app.config['ENCRYPTION_KEY'], app.config['ENCRYPTION_IV'])
        return cp.encrypt(secret)


class UserRecordVersionMismatch(ApiException):
    def __init__(self, found_ver, current_ver):
        super(ApiException, self).__init__('Found user record ver %i but current ver is %i and no upgrade path specified'
                                           % (found_ver, current_ver))


class UserCannotDescryptSecret(ApiException):
    def __init__(self):
        super(ApiException, self).__init__('User secret could not be descrypted')