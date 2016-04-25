class MusicGraphException(Exception):
    def __init__(self, msg):
        super().__init__(msg)


class SongGroupExistsException(MusicGraphException):
    def __init__(self, group_name):
        super().__init__('Song group with name %s exists' % group_name)


class EchonestApiObjectNotFoundException(MusicGraphException):
    def __init__(self, code, msg):
        super().__init__('Echonest object not found [%s] [%s]' % (code, msg))


class LibraryRecordVersionMismatch(MusicGraphException):
    def __init__(self, found_ver, current_ver):
        super().__init__('Found user record ver %i but current ver is %i and no upgrade path specified'
                         % (found_ver, current_ver))
