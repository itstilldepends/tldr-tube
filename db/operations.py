"""
Database operations for Collections and Videos.

Helper functions for CRUD operations on collections.
"""

from typing import List, Optional
from sqlalchemy.orm import Session, joinedload

from db.session import get_session
from db.models import Collection, Video, ProcessingJob


def create_collection(title: str, description: Optional[str] = None) -> Collection:
    """
    Create a new empty collection.

    Args:
        title: Collection title
        description: Optional description

    Returns:
        Created Collection object

    Example:
        >>> collection = create_collection("Python Course", "Learn Python basics")
        >>> print(collection.id)
        1
    """
    with get_session() as session:
        collection = Collection(
            title=title,
            description=description
        )
        session.add(collection)
        session.commit()
        session.refresh(collection)

        # Expunge from session to prevent DetachedInstanceError
        session.expunge(collection)
        return collection


def add_video_to_collection(video_id: int, collection_id: int) -> bool:
    """
    Add an existing video to a collection.

    Sets the video's collection_id and assigns the next order_index.

    Args:
        video_id: Database ID of the video
        collection_id: Database ID of the collection

    Returns:
        True if successful, False if video or collection not found

    Example:
        >>> add_video_to_collection(video_id=5, collection_id=1)
        True
    """
    with get_session() as session:
        video = session.query(Video).filter_by(id=video_id).first()
        collection = session.query(Collection).filter_by(id=collection_id).first()

        if not video or not collection:
            return False

        # Get max order_index in this collection
        max_order = session.query(Video).filter_by(
            collection_id=collection_id
        ).count()

        video.collection_id = collection_id
        video.order_index = max_order  # Append to end
        session.commit()
        return True


def remove_video_from_collection(video_id: int) -> bool:
    """
    Remove a video from its collection (make it standalone).

    Args:
        video_id: Database ID of the video

    Returns:
        True if successful, False if video not found

    Example:
        >>> remove_video_from_collection(video_id=5)
        True
    """
    with get_session() as session:
        video = session.query(Video).filter_by(id=video_id).first()

        if not video:
            return False

        old_collection_id = video.collection_id
        old_order = video.order_index

        # Remove from collection
        video.collection_id = None
        video.order_index = None
        session.commit()

        # Reorder remaining videos in the collection
        if old_collection_id is not None and old_order is not None:
            _reorder_collection(session, old_collection_id, old_order)

        return True


def move_video_in_collection(video_id: int, direction: str) -> bool:
    """
    Move a video up or down within its collection.

    Args:
        video_id: Database ID of the video
        direction: "up" or "down"

    Returns:
        True if successful, False if cannot move (already at edge or video not found)

    Example:
        >>> move_video_in_collection(video_id=5, direction="up")
        True
    """
    with get_session() as session:
        video = session.query(Video).filter_by(id=video_id).first()

        if not video or video.collection_id is None:
            return False

        current_order = video.order_index
        target_order = current_order - 1 if direction == "up" else current_order + 1

        # Find video at target position
        target_video = session.query(Video).filter_by(
            collection_id=video.collection_id,
            order_index=target_order
        ).first()

        if not target_video:
            return False  # Already at edge

        # Swap order_index
        video.order_index = target_order
        target_video.order_index = current_order
        session.commit()
        return True


def delete_collection(collection_id: int) -> bool:
    """
    Delete a collection and all its videos.

    Args:
        collection_id: Database ID of the collection

    Returns:
        True if deleted, False if not found

    Example:
        >>> delete_collection(collection_id=1)
        True
    """
    with get_session() as session:
        collection = session.query(Collection).filter_by(id=collection_id).first()
        if collection:
            session.delete(collection)  # Cascade will delete videos
            session.commit()
            return True
        return False


def get_all_collections() -> List[Collection]:
    """
    Get all collections with their videos.

    Returns:
        List of Collection objects ordered by creation date (newest first)

    Example:
        >>> collections = get_all_collections()
        >>> for col in collections:
        ...     print(col.title, len(col.videos))
    """
    with get_session() as session:
        # Use joinedload to eagerly load videos relationship
        # This prevents DetachedInstanceError when accessing col.videos outside session
        collections = session.query(Collection).options(
            joinedload(Collection.videos)
        ).order_by(Collection.created_at.desc()).all()

        # Access videos to ensure they're loaded before session closes
        for col in collections:
            _ = len(col.videos)  # Force load

        # Expunge all objects at once to avoid issues with shared references
        session.expunge_all()

        return collections


def _reorder_collection(session: Session, collection_id: int, removed_index: int):
    """
    Reorder videos in a collection after one is removed.

    Decrements order_index for all videos after the removed position.

    Args:
        session: SQLAlchemy session
        collection_id: Collection to reorder
        removed_index: Index of the removed video
    """
    videos = session.query(Video).filter(
        Video.collection_id == collection_id,
        Video.order_index > removed_index
    ).all()

    for video in videos:
        video.order_index -= 1

    session.commit()


# ──────────────────────────────────────────────
# ProcessingJob operations
# ──────────────────────────────────────────────

def create_job(
    url: str,
    force_asr: bool = False,
    whisper_model: str = "medium",
    provider: Optional[str] = None,
    model: Optional[str] = None,
    collection_id: Optional[int] = None,
    order_index: Optional[int] = None,
) -> ProcessingJob:
    """
    Create a new pending processing job and add it to the queue.

    Args:
        url: YouTube, Bilibili, or DeepLearning.AI video URL
        force_asr: Skip platform captions and use Whisper
        whisper_model: Whisper model size
        provider: LLM provider name
        model: LLM model name
        collection_id: Optional collection this job belongs to
        order_index: Optional position within the collection

    Returns:
        Created ProcessingJob object

    Example:
        >>> job = create_job("https://www.youtube.com/watch?v=abc123", provider="deepseek")
        >>> print(job.status)
        'pending'
    """
    with get_session() as session:
        job = ProcessingJob(
            url=url,
            force_asr=force_asr,
            whisper_model=whisper_model,
            provider=provider,
            model=model,
            collection_id=collection_id,
            order_index=order_index,
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        session.expunge(job)
    return job


def get_all_jobs(limit: int = 50) -> List[ProcessingJob]:
    """
    Get recent processing jobs ordered newest first.

    Eagerly loads result_video relationship.

    Args:
        limit: Maximum number of jobs to return

    Returns:
        List of ProcessingJob objects
    """
    from sqlalchemy.orm import joinedload as _joinedload

    with get_session() as session:
        jobs = (
            session.query(ProcessingJob)
            .options(_joinedload(ProcessingJob.result_video))
            .order_by(ProcessingJob.created_at.desc())
            .limit(limit)
            .all()
        )
        session.expunge_all()
    return jobs


def get_job(job_id: int) -> Optional[ProcessingJob]:
    """
    Get a single processing job by ID.

    Args:
        job_id: ProcessingJob primary key

    Returns:
        ProcessingJob if found, None otherwise
    """
    with get_session() as session:
        job = session.query(ProcessingJob).filter_by(id=job_id).first()
        if job:
            session.expunge(job)
    return job
