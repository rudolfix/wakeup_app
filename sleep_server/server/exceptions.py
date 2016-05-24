from common.exceptions import ApiException


class MusicGraphException(Exception):
    def __init__(self, msg):
        super().__init__(msg)


class SongGroupExistsException(MusicGraphException):
    def __init__(self, group_name):
        super().__init__('Song group with name %s exists' % group_name)


class EchonestApiObjectNotFoundException(MusicGraphException):
    def __init__(self, code, msg):
        super().__init__('Echonest object not found [%s] [%s]' % (code, msg))


class LibraryRecordVersionMismatchException(MusicGraphException):
    def __init__(self, found_ver, current_ver):
        super().__init__('Found user record ver %i but current ver is %i and no upgrade path specified'
                         % (found_ver, current_ver))


class CacheEntryNotExistsException(MusicGraphException):
    def __init__(self, entry_name):
        super().__init__('Cache entry %s does not exist' % entry_name)


class CacheRecordVersionMismatchException(MusicGraphException):
    def __init__(self, found_ver, current_ver, entry_name):
        super().__init__('Found cache record %s ver %i but current ver is %i' % (entry_name, found_ver, current_ver))


class MqMalformedMessageException(MusicGraphException):
    def __init__(self, errstr):
        super().__init__('MQ body malformed, message is discarded (%s)' % errstr)
