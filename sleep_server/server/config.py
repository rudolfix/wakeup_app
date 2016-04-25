from common.config import ConfigBase


class Config(ConfigBase):
    ECHONEST_API_KEYS = ['UFIOCP1DHXIKUMV2H', 'PTELLTDHNE6QEG42C', '9UGMUXTCZ2WT7WWMJ']
    # JGJCRKWLXLBZIFAZB 120 api calls rate limit
    # PTELLTDHNE6QEG42C 20 api calls rate limit
    # 9UGMUXTCZ2WT7WWMJ 20
    # V91CRTEB0IFMAJBMB 120 but they disabled ;>
    HOST_NAME = 'dev.wakeupapp.com'
    TESTING = False
    SQLALCHEMY_DATABASE_URI = 'mysql://dev@localhost/music_graph_dev2'
    DEBUG = True
    USER_STORAGE_URI = '/home/vagrant/user_storage/'
