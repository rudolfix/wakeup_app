from common.config import ConfigBase
import logging


class Config(ConfigBase):
    ECHONEST_API_KEYS = ['UFIOCP1DHXIKUMV2H', 'PTELLTDHNE6QEG42C', '9UGMUXTCZ2WT7WWMJ']
    # JGJCRKWLXLBZIFAZB 120 api calls rate limit
    # PTELLTDHNE6QEG42C 20 api calls rate limit
    # 9UGMUXTCZ2WT7WWMJ 20
    # V91CRTEB0IFMAJBMB 120 but they disabled ;>
    TESTING = False
    SQLALCHEMY_DATABASE_URI = 'mysql://dev@localhost/music_graph_dev2'
    SQLALCHEMY_POOL_RECYCLE = 60*5  # in seconds
    DEBUG = True
    USER_STORAGE_URI = '/home/vagrant/user_storage/'
    FLASK_PIKA_PARAMS = {
        'host': 'localhost',  # amqp.server.com
        'username': 'guest',  # convenience param for username
        'password': 'guest',  # convenience param for password
        # 'port': 5672,  # amqp server port
        # 'virtual_host': 'vhost'  # amqp vhost
    }
    FLASK_PIKA_POOL_PARAMS = None  # it seems connection pool does not work correctly in fpika
    # {
    #     'pool_size': 8 + 2,  # 2 channels for in process consumers
    #     'pool_recycle': 600
    # }
    # logging
    LOG_FILE = '/var/log/sleep_server/server.log'
    LOG_LEVEL = logging.DEBUG
