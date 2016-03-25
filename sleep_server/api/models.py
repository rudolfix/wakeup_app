# coding: utf-8
# sqlacodegen mysql://dev@localhost/music_graph > models.py
from api import db
from sqlalchemy import Column, Float, ForeignKey, Integer, String, DateTime
from sqlalchemy.orm import relationship
import datetime


Base = db.Model
metadata = Base.metadata


class ArtistGenres(Base):
    __tablename__ = 'ArtistGenres'

    ArtistId = Column('ArtistId', ForeignKey('Artists.ArtistId'), primary_key=True, nullable=False)
    GenreId = Column('GenreId', ForeignKey('Genres.GenreId'), primary_key=True, nullable=False, index=True)
    Ord = Column(Integer, nullable=False)

    Genre = relationship('Genre')


class Artist(Base):
    __tablename__ = 'Artists'

    ArtistId = Column(Integer, primary_key=True, unique=True, autoincrement=True)
    Name = Column(String(128, 'utf8_unicode_ci'), nullable=False)
    SpotifyId = Column(String(128), nullable=False, unique=True)
    EchonestId = Column(String(128), nullable=False, unique=True)
    Hotness = Column(Float, nullable=False)

    Genres = relationship('ArtistGenres')


class Genre(Base):
    __tablename__ = 'Genres'

    GenreId = Column(Integer, primary_key=True, unique=True, autoincrement=True)
    Name = Column(String(64, 'utf8_unicode_ci'), nullable=False, unique=True)


class SongTracks(Base):
    __tablename__ = 'SongTracks'

    SongId = Column(ForeignKey('Songs.SongId'), nullable=False, index=True)
    SpotifyId = Column(String(128, 'utf8_unicode_ci'), primary_key=True, unique=True)
    EchonestId = Column(String(129, 'utf8_unicode_ci'), nullable=False, unique=True)


class Song(Base):
    __tablename__ = 'Songs'

    SongId = Column(Integer, primary_key=True, unique=True, autoincrement=True)
    EchonestId = Column(String(128), nullable=False, unique=True)
    Name = Column(String(128, 'utf8_unicode_ci'), nullable=False)
    ArtistId = Column(ForeignKey('Artists.ArtistId'), nullable=False, index=True)
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

    Artist = relationship('Artist')
    Genre = relationship('Genre')
    Tracks = relationship('SongTracks')
