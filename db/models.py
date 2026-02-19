"""
SQLAlchemy models for tldr-tube.

Models:
- Collection: Group of related videos (e.g., a course)
- Video: Individual video with metadata and summary
- Segment: Time-stamped summary segment within a video
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Collection(Base):
    """A collection of related videos (e.g., a course with multiple lectures)."""

    __tablename__ = "collections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    videos = relationship("Video", back_populates="collection", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Collection(id={self.id}, title='{self.title}', videos={len(self.videos)})>"


class Video(Base):
    """A video with its transcript, summary, and metadata."""

    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Source information
    source_type = Column(String(50), nullable=False)  # "youtube" | "local" | "s3"
    source_url = Column(String(1000), nullable=False)
    video_id = Column(String(255), unique=True, nullable=False, index=True)

    # Metadata
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)       # Video description (can be long, useful for search/context)
    upload_date = Column(String(20), nullable=True)  # Upload date in YYYY-MM-DD format
    tags = Column(Text, nullable=True)              # Tags as JSON array string
    duration_seconds = Column(Integer, nullable=True)
    channel_name = Column(String(255), nullable=True)
    thumbnail_url = Column(String(1000), nullable=True)

    # Content
    raw_transcript = Column(Text, nullable=False)  # JSON string: [{"start": ..., "duration": ..., "text": ...}]
    video_type = Column(String(50), nullable=False)  # "tutorial" | "podcast" | "lecture" | "other"

    # Summaries (bilingual)
    tldr = Column(Text, nullable=False)             # English TL;DR
    tldr_zh = Column(Text, nullable=False)          # Chinese TL;DR

    transcript_source = Column(String(50), nullable=False)  # "youtube_api" | "whisper"

    # Collection relationship
    collection_id = Column(Integer, ForeignKey("collections.id"), nullable=True, index=True)
    order_index = Column(Integer, nullable=True)

    # Timestamps
    processed_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    collection = relationship("Collection", back_populates="videos")
    segments = relationship("Segment", back_populates="video", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Video(id={self.id}, video_id='{self.video_id}', title='{self.title[:30]}...')>"


class Segment(Base):
    """A time-stamped summary segment within a video."""

    __tablename__ = "segments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False, index=True)

    # Time range
    start_seconds = Column(Float, nullable=False)
    end_seconds = Column(Float, nullable=False)
    timestamp = Column(String(20), nullable=False)  # "MM:SS" format for display

    # Content (bilingual)
    summary = Column(Text, nullable=False)          # English summary
    summary_zh = Column(Text, nullable=False)       # Chinese summary

    # Relationships
    video = relationship("Video", back_populates="segments")

    def __repr__(self):
        return f"<Segment(id={self.id}, timestamp='{self.timestamp}', video_id={self.video_id})>"
