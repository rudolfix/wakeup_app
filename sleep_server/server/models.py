# coding: utf-8
# sqlacodegen mysql://dev@localhost/music_graph > models.py
from server import db
from sqlalchemy import Column, Float, ForeignKey, Integer, String, DateTime
from sqlalchemy.orm import relationship, validates
import datetime
from enum import Enum


class GenreSourceType(Enum):
    echonest = 1,
    infered = 2


class Validators:
    def _max_len_truncate(self, key, value):
        return Validators.max_len_truncate(self.__class__, key, value)

    @staticmethod
    def max_len_truncate(cls, key, value):
        max_len = getattr(cls, key).prop.columns[0].type.length
        if value and len(value) > max_len:
            return value[:max_len]
        return value

Base = db.Model
metadata = Base.metadata


class ArtistGenres(Base):
    __tablename__ = 'ArtistGenres'

    ArtistId = Column('ArtistId', ForeignKey('Artists.ArtistId', ondelete='CASCADE'), primary_key=True, nullable=False)
    GenreId = Column('GenreId', ForeignKey('Genres.GenreId'), primary_key=True, nullable=False, index=True)
    Ord = Column(Integer, nullable=False)
    SourceType = Column(Integer, nullable=False)

    Genre = relationship('Genre')


class ArtistAdditionalSpotifyIds(Base):
    __tablename__ = 'ArtistAdditionalSpotifyIds'

    ArtistId = Column(ForeignKey('Artists.ArtistId', ondelete='CASCADE'), nullable=False, index=True)
    SpotifyId = Column(String(128), primary_key=True, unique=True)

    # Artist = relationship('Artist')


class Artist(Base, Validators):
    __tablename__ = 'Artists'

    ArtistId = Column(Integer, primary_key=True, unique=True, autoincrement=True)
    Name = Column(String(128, 'utf8_unicode_ci'), nullable=False)
    SpotifyId = Column(String(128), nullable=False, unique=True)
    EchonestId = Column(String(128), nullable=False, unique=True)
    SpotifyStatus = Column(Integer, nullable=False, default=0)
    Hotness = Column(Float, nullable=False)
    InsertedAt = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    UpdatedAt = Column(DateTime, nullable=False)
    SimilarArtistsUpdatedAt = Column(DateTime)

    Genres = relationship('ArtistGenres', cascade="all, delete-orphan")
    AdditionalSpotifyIds = relationship('ArtistAdditionalSpotifyIds', cascade="all, delete-orphan")

    @validates('Name')
    def validate_name(self, key, value):
        return self._max_len_truncate(key, value)


class Genre(Base):
    __tablename__ = 'Genres'

    GenreId = Column(Integer, primary_key=True, unique=True, autoincrement=True)
    Name = Column(String(64, 'utf8_unicode_ci'), nullable=False, unique=True)


class Group(Base, Validators):
    __tablename__ = 'Groups'

    GroupId = Column(Integer, primary_key=True)
    Name = Column(String(128, 'utf8_unicode_ci'), nullable=False, unique=False)
    UniqueRef = Column(String(128, 'utf8_unicode_ci'), nullable=False, unique=True)
    Type = Column(Integer, nullable=False)

    @validates('Name')
    def validate_name(self, key, value):
        return self._max_len_truncate(key, value)


class SimilarArtist(Base):
    __tablename__ = 'SimilarArtists'

    ArtistId = Column(ForeignKey('Artists.ArtistId', ondelete='CASCADE'), primary_key=True, nullable=False)
    SimilarArtistId = Column(ForeignKey('Artists.ArtistId', ondelete='CASCADE'), primary_key=True, nullable=False, index=True)
    Dist = Column(Float)

    Artist = relationship('Artist', primaryjoin='SimilarArtist.ArtistId == Artist.ArtistId')
    Artist1 = relationship('Artist', primaryjoin='SimilarArtist.SimilarArtistId == Artist.ArtistId')


class SimilarGenre(Base):
    __tablename__ = 'SimilarGenres'

    GenreId = Column(ForeignKey('Genres.GenreId'), primary_key=True, nullable=False)
    SimilarGenreId = Column(ForeignKey('Genres.GenreId'), primary_key=True, nullable=False, index=True)
    Similarity = Column(Float, nullable=False)

    Genre = relationship('Genre', primaryjoin='SimilarGenre.GenreId == Genre.GenreId')
    Genre1 = relationship('Genre', primaryjoin='SimilarGenre.SimilarGenreId == Genre.GenreId')


class SongGroup(Base):
    __tablename__ = 'SongGroups'

    GroupId = Column(ForeignKey('Groups.GroupId', ondelete='CASCADE'), primary_key=True, nullable=False, index=True)
    SongId = Column(ForeignKey('Songs.SongId', ondelete='CASCADE'), primary_key=True, nullable=False, index=True)
    Ord = Column(Integer, nullable=False)

    Group = relationship('Group')
    Song = relationship('Song')


class SongTracks(Base):
    __tablename__ = 'SongTracks'

    SongId = Column(ForeignKey('Songs.SongId', ondelete='CASCADE'), nullable=False, index=True)
    SpotifyId = Column(String(128, 'utf8_unicode_ci'), primary_key=True, unique=True)
    EchonestId = Column(String(129, 'utf8_unicode_ci'), nullable=False, unique=True)


class Song(Base, Validators):
    __tablename__ = 'Songs'

    SongId = Column(Integer, primary_key=True, unique=True, autoincrement=True)
    EchonestId = Column(String(128), nullable=False, unique=True)
    Name = Column(String(128, 'utf8_unicode_ci'), nullable=False)
    ArtistId = Column(ForeignKey('Artists.ArtistId', ondelete='CASCADE'), nullable=False, index=True)
    GenreId = Column(ForeignKey('Genres.GenreId'), index=True)
    DurationMs = Column(Integer, nullable=False)
    Hotness = Column(Float, nullable=False)
    IsToplistSong = Column(Integer, nullable=False, default=0)
    AS_key = Column(Integer, nullable=True)
    AS_energy = Column(Float, nullable=True)
    AS_liveness = Column(Float, nullable=True)
    AS_tempo = Column(Float, nullable=True)
    AS_speechiness = Column(Float, nullable=True)
    AS_acousticness = Column(Float, nullable=True)
    AS_instrumentalness = Column(Float, nullable=True)
    AS_mode = Column(Integer, nullable=True)
    AS_time_signature = Column(Integer, nullable=True)
    AS_loudness = Column(Integer, nullable=True)
    AS_valence = Column(Float, nullable=True)
    AS_danceability = Column(Float, nullable=True)
    InsertedAt = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)
    UpdatedAt = Column(DateTime(timezone=True), nullable=False)

    Artist = relationship('Artist')
    Genre = relationship('Genre')
    Tracks = relationship('SongTracks')

    @validates('Name')
    def validate_name(self, key, value):
        return self._max_len_truncate(key, value)