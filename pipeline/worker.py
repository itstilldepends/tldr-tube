"""
Background queue worker for video processing.

Runs a single daemon thread that polls the ProcessingJob table for pending
jobs and processes them one at a time using process_video().

Progress is stored in two tiers:
- In-memory (_progress dict): fine-grained, per-step, lost on process restart
- DB (current_step column): last step only, survives browser tab close and restart

Public API:
    start_queue_worker()       -- start the daemon thread (idempotent)
    get_job_progress(job_id)   -- return list of step strings for a job
"""

import os
import threading
import time
import logging
from datetime import datetime
from typing import Optional

from db.session import get_session
from db.models import ProcessingJob

logger = logging.getLogger(__name__)

# ── Singletons ────────────────────────────────────────────────────────────────

_worker_thread: Optional[threading.Thread] = None
_progress: dict[int, list[str]] = {}   # job_id → accumulated step messages
_progress_lock = threading.Lock()

POLL_INTERVAL = 3   # seconds to wait when queue is empty


# ── Public API ────────────────────────────────────────────────────────────────

def start_queue_worker() -> None:
    """
    Start the background worker thread if not already running.

    Safe to call multiple times — only one thread will run at a time.
    The thread is a daemon so it exits automatically when the process exits.
    """
    global _worker_thread
    if _worker_thread is None or not _worker_thread.is_alive():
        _reset_stuck_jobs()
        _worker_thread = threading.Thread(
            target=_worker_loop,
            name="tldr-tube-worker",
            daemon=True,
        )
        _worker_thread.start()
        logger.info("Queue worker thread started")


def get_job_progress(job_id: int) -> list[str]:
    """
    Return the in-memory progress steps accumulated for a job.

    Returns an empty list if the job is not currently being tracked
    (e.g. after a process restart — fall back to job.current_step instead).

    Args:
        job_id: ProcessingJob primary key

    Returns:
        List of formatted step strings, e.g. ["✅ Fetching metadata", "⏳ Generating summary..."]
    """
    with _progress_lock:
        return list(_progress.get(job_id, []))


# ── Internal ──────────────────────────────────────────────────────────────────

def _worker_loop() -> None:
    """Main loop: claim and process one job at a time, sleep when idle."""
    while True:
        try:
            job = _claim_next_pending()
            if job:
                _process_job(job)
            else:
                time.sleep(POLL_INTERVAL)
        except Exception as e:
            logger.exception(f"Unexpected error in worker loop: {e}")
            time.sleep(POLL_INTERVAL)


def _claim_next_pending() -> Optional[ProcessingJob]:
    """
    Atomically claim the oldest pending job by setting its status to 'processing'.

    Returns the claimed job (expunged from session), or None if queue is empty.
    """
    with get_session() as session:
        job = (
            session.query(ProcessingJob)
            .filter_by(status="pending")
            .order_by(ProcessingJob.created_at)
            .first()
        )
        if job is None:
            return None

        job.status = "processing"
        job.started_at = datetime.utcnow()
        session.commit()
        session.refresh(job)
        session.expunge(job)
        return job


def _update_job_step(job_id: int, step: str, state: str) -> None:
    """Write a progress step to in-memory store and persist current_step to DB."""
    icon = "✅" if state == "success" else "❌" if state == "error" else "⏳"
    message = f"{icon} {step}"

    with _progress_lock:
        if job_id not in _progress:
            _progress[job_id] = []
        _progress[job_id].append(message)

    # Persist last step to DB so UI can recover after tab close
    try:
        with get_session() as session:
            j = session.query(ProcessingJob).filter_by(id=job_id).first()
            if j:
                j.current_step = message
                session.commit()
    except Exception as e:
        logger.warning(f"Could not persist current_step for job {job_id}: {e}")


def _process_job(job: ProcessingJob) -> None:
    """
    Process a single job end-to-end, updating status on completion or failure.

    Args:
        job: A ProcessingJob with status='processing' (already claimed)
    """
    # Initialise in-memory progress list for this job
    with _progress_lock:
        _progress[job.id] = []

    logger.info(f"Processing job {job.id} (type={job.job_type}): {job.url}")

    def status_callback(step: str, state: str) -> None:
        _update_job_step(job.id, step, state)

    try:
        if job.job_type == "generate_notes":
            _run_notes_job(job, status_callback)
        else:
            _run_video_job(job, status_callback)

    except Exception as e:
        error_msg = str(e)
        logger.exception(f"Job {job.id} failed: {error_msg}")

        with _progress_lock:
            if job.id in _progress:
                _progress[job.id].append(f"❌ Failed: {error_msg}")

        with get_session() as session:
            j = session.query(ProcessingJob).filter_by(id=job.id).first()
            if j:
                j.status = "failed"
                j.completed_at = datetime.utcnow()
                j.error_message = error_msg
                j.current_step = f"❌ Failed: {error_msg}"
                session.commit()


def _run_video_job(job: ProcessingJob, status_callback) -> None:
    """Process a video summarization job."""
    from pipeline.processor import process_video

    video = process_video(
        url=job.url,
        collection_id=job.collection_id,
        order_index=job.order_index,
        status_callback=status_callback,
        force_asr=job.force_asr,
        whisper_model=job.whisper_model,
        provider=job.provider,
        model=job.model,
    )

    with get_session() as session:
        j = session.query(ProcessingJob).filter_by(id=job.id).first()
        j.status = "completed"
        j.completed_at = datetime.utcnow()
        j.result_video_id = video.id
        j.current_step = "✅ Done"
        session.commit()

    logger.info(f"Job {job.id} completed (video id={video.id})")


def _run_notes_job(job: ProcessingJob, status_callback) -> None:
    """Generate keyframe notes for an existing video."""
    import json
    from db.models import Video, Segment, Keyframe, Note
    from pipeline.keyframes import extract_keyframes, get_deeplearning_video_url, get_video_stream_url, download_video_for_keyframes
    from pipeline.keyframe_notes import generate_keyframe_notes

    def note_status(msg: str):
        status_callback(msg, "processing")

    # Load video from DB
    with get_session() as session:
        video = session.query(Video).filter_by(id=job.target_video_id).first()
        if not video:
            raise ValueError(f"Video id={job.target_video_id} not found")
        video_id_str = video.video_id
        source_type = video.source_type
        source_url = video.source_url
        db_video_id = video.id
        transcript = json.loads(video.raw_transcript)
        tldr = video.tldr
        duration = video.duration_seconds
        segments = [
            {"start_seconds": s.start_seconds, "end_seconds": s.end_seconds, "summary": s.summary}
            for s in session.query(Segment).filter_by(video_id=video.id).order_by(Segment.start_seconds).all()
        ]

    # Clean up old keyframes directory on regenerate
    import shutil
    output_dir = f"data/keyframes/{video_id_str}"
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)

    # Get video URL for keyframe extraction
    downloaded_video = None
    if source_type == "deeplearning_ai":
        note_status("Fetching video stream URL...")
        video_url = get_deeplearning_video_url(source_url)
    elif source_type == "bilibili":
        note_status("Downloading video for keyframe extraction...")
        video_url = download_video_for_keyframes(source_url, output_dir)
        downloaded_video = video_url
    else:
        note_status("Fetching video stream URL...")
        video_url = get_video_stream_url(source_url)

    # Extract keyframes
    keyframes = extract_keyframes(video_url, output_dir, note_status)

    # Clean up downloaded video file (Bilibili)
    if downloaded_video and os.path.exists(downloaded_video):
        os.remove(downloaded_video)

    # Generate notes
    merge = job.merge_batches if job.merge_batches is not None else True
    notes = generate_keyframe_notes(
        keyframes=keyframes,
        transcript=transcript,
        video_duration=duration,
        tldr=tldr,
        segments=segments,
        status_callback=note_status,
        merge_batches=merge,
    )

    # Persist to DB
    with get_session() as session:
        session.query(Note).filter_by(video_id=db_video_id).delete()
        session.query(Keyframe).filter_by(video_id=db_video_id).delete()

        # Save keyframes
        kf_id_map = {}
        for i, kf in enumerate(keyframes):
            db_kf = Keyframe(
                video_id=db_video_id,
                timestamp_seconds=float(kf.timestamp),
                timestamp_str=kf.timestamp_str,
                frame_path=kf.path,
                sharpness=kf.sharpness,
                is_visual=kf.is_visual,
            )
            session.add(db_kf)
            session.flush()
            kf_id_map[i] = db_kf.id

        # Save notes
        visual_kf_indices = [i for i, kf in enumerate(keyframes) if kf.is_visual]
        for order, note in enumerate(notes):
            db_kf_ids = []
            for vi in note.keyframe_indices:
                if vi < len(visual_kf_indices):
                    global_idx = visual_kf_indices[vi]
                    if global_idx in kf_id_map:
                        db_kf_ids.append(kf_id_map[global_idx])
            db_note = Note(
                video_id=db_video_id,
                order_index=order,
                title=note.title,
                title_zh=note.title_zh,
                notes=note.notes,
                notes_zh=note.notes_zh,
                keyframe_ids=json.dumps(db_kf_ids),
            )
            session.add(db_note)
        session.commit()

    # Clean up unreferenced keyframe images
    referenced_paths = {kf.path for kf in keyframes if kf.is_visual}
    for fname in os.listdir(output_dir):
        fpath = os.path.join(output_dir, fname)
        if fpath not in referenced_paths and fname.endswith(".jpg"):
            os.remove(fpath)
            logger.debug(f"Removed unreferenced keyframe: {fpath}")

    with get_session() as session:
        j = session.query(ProcessingJob).filter_by(id=job.id).first()
        j.status = "completed"
        j.completed_at = datetime.utcnow()
        j.result_video_id = db_video_id
        j.current_step = f"✅ Generated {len(notes)} notes"
        session.commit()

    logger.info(f"Notes job {job.id} completed: {len(notes)} notes for video {db_video_id}")


def _reset_stuck_jobs() -> None:
    """Reset any 'processing' jobs left over from a previous crash back to 'pending'."""
    try:
        with get_session() as session:
            stuck = session.query(ProcessingJob).filter_by(status="processing").all()
            for job in stuck:
                job.status = "pending"
                job.started_at = None
                job.current_step = None
            if stuck:
                session.commit()
                logger.info(f"Reset {len(stuck)} stuck job(s) to pending on startup")
    except Exception as e:
        logger.warning(f"Could not reset stuck jobs: {e}")
