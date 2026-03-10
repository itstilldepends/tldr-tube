"""
Keyframe extraction pipeline for lecture videos.

Extracts representative keyframes from video using:
1. 1fps frame extraction (ffmpeg)
2. Dark frame filtering
3. pHash coarse filter (consecutive comparison, keep last of stable period)
4. SSIM fine filter (catch pHash false positives)
5. Debounce (animation settling)
6. Global dedup (recurring slides)
7. Blur replacement (sample sharper nearby frames)

Functions:
- extract_keyframes: Full pipeline from video URL to keyframe paths
- get_deeplearning_video_url: Extract HLS URL from DeepLearning.AI page
"""

import os
import re
import json
import subprocess
import shutil
import time
import logging
from dataclasses import dataclass
from typing import Optional, Callable

import requests
import imagehash
from PIL import Image
import cv2
from skimage.metrics import structural_similarity as ssim

logger = logging.getLogger(__name__)

# Tested thresholds (validated on DeepLearning.AI content)
BRIGHTNESS_THRESHOLD = 15
PHASH_THRESHOLD = 5
SSIM_THRESHOLD = 0.85
DEBOUNCE_WINDOW = 4
GLOBAL_DEDUP_THRESHOLD = 12
BLUR_ABS_THRESHOLD = 300.0
BLUR_REL_THRESHOLD = 0.85
VISUAL_SHARPNESS_THRESHOLD = 600


@dataclass
class KeyframeInfo:
    """Information about an extracted keyframe."""
    path: str
    timestamp: int  # seconds
    timestamp_str: str  # "MM:SS"
    sharpness: float
    is_visual: bool  # True = slide/code, False = talking head


def format_time(seconds: int) -> str:
    """Format seconds as MM:SS."""
    m, s = divmod(seconds, 60)
    return f"{m:02d}:{s:02d}"


def frame_to_seconds(path: str) -> int:
    """Extract timestamp from frame filename. frame_00001.jpg -> 0 (0-indexed)."""
    name = os.path.basename(path)
    num = int(re.search(r"(\d+)", name).group(1))
    return num - 1  # ffmpeg starts at 00001


def laplacian_variance(path: str) -> float:
    """Compute Laplacian variance as a sharpness score. Higher = sharper."""
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    return cv2.Laplacian(img, cv2.CV_64F).var()


# ── Video URL extraction ────────────────────────────────────────────────────

def get_deeplearning_video_url(page_url: str) -> str:
    """Extract HLS video stream URL from a DeepLearning.AI lesson page."""
    resp = requests.get(page_url, timeout=15)
    resp.raise_for_status()

    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', resp.text, re.DOTALL)
    if not match:
        raise Exception("Could not find __NEXT_DATA__ in page")

    data = json.loads(match.group(1))
    trpc_state = data["props"]["pageProps"]["trpcState"]

    for query in trpc_state.get("json", {}).get("queries", []):
        key = query.get("queryKey", [])
        if key and isinstance(key[0], list):
            if "getLessonVideo" in key[0] and "getLessonVideoSubtitle" not in key[0]:
                return query["state"]["data"]["video"]["mp4Url"].strip()

    raise Exception("Could not find video URL in page data")


def get_youtube_video_url(video_url: str) -> str:
    """Get a direct video stream URL from YouTube using yt-dlp.

    Returns a URL that ffmpeg can consume directly (no download needed).
    """
    import yt_dlp

    ydl_opts = {
        "format": "bestvideo[height<=720][ext=mp4]/best[height<=720]",
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=False)
        return info["url"]


# ── Frame extraction ────────────────────────────────────────────────────────

def _extract_frames(video_url: str, output_dir: str, status_callback: Optional[Callable] = None) -> list[str]:
    """Extract frames at 1fps using ffmpeg."""
    os.makedirs(output_dir, exist_ok=True)

    cmd = [
        "ffmpeg", "-i", video_url,
        "-vf", "fps=1,scale=1280:-1",
        "-q:v", "3",
        os.path.join(output_dir, "frame_%05d.jpg"),
        "-y", "-loglevel", "warning"
    ]

    if status_callback:
        status_callback("Extracting frames at 1fps...")
    start = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg frame extraction failed (exit {result.returncode}): {result.stderr[:500]}")
    elapsed = time.time() - start

    frames = sorted(
        [os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.startswith("frame_")],
    )
    logger.info(f"Extracted {len(frames)} frames in {elapsed:.1f}s")
    return frames


def _filter_dark_frames(frame_paths: list[str]) -> list[str]:
    """Remove near-black frames (intro/outro/transitions)."""
    return [
        p for p in frame_paths
        if (img := cv2.imread(p, cv2.IMREAD_GRAYSCALE)) is not None
        and img.mean() > BRIGHTNESS_THRESHOLD
    ]


def _coarse_filter(frame_paths: list[str]) -> list[str]:
    """pHash coarse filter: keep last frame of each stable period."""
    if not frame_paths:
        return []

    prev_hash = imagehash.phash(Image.open(frame_paths[0]))
    segment_last = frame_paths[0]
    candidates = []

    for path in frame_paths[1:]:
        h = imagehash.phash(Image.open(path))
        if prev_hash - h >= PHASH_THRESHOLD:
            candidates.append(segment_last)
        segment_last = path
        prev_hash = h

    candidates.append(segment_last)
    return candidates


def _fine_filter(candidates: list[str]) -> list[str]:
    """SSIM fine filter: catch pHash false positives."""
    if not candidates:
        return []

    keyframes = [candidates[0]]
    prev = cv2.imread(candidates[0], cv2.IMREAD_GRAYSCALE)
    prev = cv2.resize(prev, (640, 360))

    for path in candidates[1:]:
        curr = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        curr = cv2.resize(curr, (640, 360))
        score, _ = ssim(prev, curr, full=True)
        if score >= SSIM_THRESHOLD:
            keyframes[-1] = path
        else:
            keyframes.append(path)
        prev = curr

    return keyframes


def _debounce(keyframe_paths: list[str]) -> list[str]:
    """Keep the last frame in each burst within debounce window."""
    if not keyframe_paths:
        return []

    times = [frame_to_seconds(p) for p in keyframe_paths]
    path_by_time = dict(zip(times, keyframe_paths))

    result_times = []
    i = 0
    while i < len(times):
        j = i
        while j < len(times) - 1 and times[j + 1] - times[i] < DEBOUNCE_WINDOW:
            j += 1
        result_times.append(times[j])
        i = j + 1

    return [path_by_time[t] for t in result_times]


def _global_dedup(keyframe_paths: list[str]) -> list[str]:
    """Remove globally duplicate slides."""
    if not keyframe_paths:
        return []

    hashes = [(p, imagehash.phash(Image.open(p))) for p in keyframe_paths]
    seen: list[tuple[str, imagehash.ImageHash]] = []

    for path, h in hashes:
        if not any(h - seen_h < GLOBAL_DEDUP_THRESHOLD for _, seen_h in seen):
            seen.append((path, h))

    return [p for p, _ in seen]


def _replace_blurry_frames(
    keyframe_paths: list[str],
    video_url: str,
    output_dir: str,
    status_callback: Optional[Callable] = None,
) -> list[str]:
    """Replace blurry keyframes by sampling sharper frames from the video."""
    scores = [laplacian_variance(p) for p in keyframe_paths]
    result = []

    for i, (path, score) in enumerate(zip(keyframe_paths, scores)):
        neighbors = []
        for j in range(max(0, i - 2), min(len(scores), i + 3)):
            if j != i:
                neighbors.append(scores[j])
        neighbor_median = sorted(neighbors)[len(neighbors) // 2] if neighbors else score

        is_abs_blurry = score < BLUR_ABS_THRESHOLD
        is_rel_blurry = neighbor_median > 0 and score < BLUR_REL_THRESHOLD * neighbor_median

        if not is_abs_blurry and not is_rel_blurry:
            result.append(path)
            continue

        t = frame_to_seconds(path)
        logger.info(f"Blurry frame at {format_time(t)} (sharpness={score:.0f}), sampling replacement...")

        best_path, best_score = _sample_sharp_replacement(video_url, float(t), output_dir)

        if best_path and best_score > score:
            shutil.copy2(best_path, path)
            logger.info(f"  Replaced with sharpness={best_score:.0f}")

        tmp_dir = os.path.join(output_dir, f"_blur_sample_{t}")
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)

        result.append(path)

    return result


def _sample_sharp_replacement(
    video_url: str, timestamp: float, output_dir: str,
    radius: float = 1.0, sample_fps: int = 10,
) -> tuple[Optional[str], float]:
    """Sample frames at high fps around timestamp and return the sharpest."""
    start = max(0, timestamp - radius)
    duration = radius * 2

    tmp_dir = os.path.join(output_dir, f"_blur_sample_{int(timestamp)}")
    os.makedirs(tmp_dir, exist_ok=True)

    cmd = [
        "ffmpeg", "-ss", str(start), "-i", video_url,
        "-t", str(duration),
        "-vf", f"fps={sample_fps},scale=1280:-1",
        "-q:v", "3",
        os.path.join(tmp_dir, "s_%03d.jpg"),
        "-y", "-loglevel", "warning"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.warning(f"Blur replacement sampling failed: {result.stderr[:200]}")
        return None, -1.0

    best_path = None
    best_score = -1.0
    for f in os.listdir(tmp_dir):
        if not f.endswith(".jpg"):
            continue
        p = os.path.join(tmp_dir, f)
        s = laplacian_variance(p)
        if s > best_score:
            best_score = s
            best_path = p

    return best_path, best_score


# ── Main pipeline ───────────────────────────────────────────────────────────

def extract_keyframes(
    video_url: str,
    output_dir: str,
    status_callback: Optional[Callable] = None,
) -> list[KeyframeInfo]:
    """Run the full keyframe extraction pipeline.

    Args:
        video_url: HLS stream URL or local video path
        output_dir: Directory to store final keyframe images (e.g. data/keyframes/{video_id})
        status_callback: Optional function to report progress

    Returns:
        List of KeyframeInfo with paths, timestamps, and metadata
    """
    os.makedirs(output_dir, exist_ok=True)
    frames_dir = os.path.join(output_dir, "_all_frames")

    try:
        # Step 1: Extract frames
        if status_callback:
            status_callback("Extracting frames...")
        all_frames = _extract_frames(video_url, frames_dir, status_callback)
        logger.info(f"Step 1: {len(all_frames)} frames extracted")

        # Step 1.5: Filter dark frames
        bright_frames = _filter_dark_frames(all_frames)
        logger.info(f"Step 1.5: {len(all_frames)} → {len(bright_frames)} after dark filter")

        # Step 2: pHash coarse filter
        if status_callback:
            status_callback("Filtering keyframes (pHash)...")
        candidates = _coarse_filter(bright_frames)
        logger.info(f"Step 2: {len(bright_frames)} → {len(candidates)} after pHash")

        # Step 3: SSIM fine filter
        if status_callback:
            status_callback("Filtering keyframes (SSIM)...")
        keyframes = _fine_filter(candidates)
        logger.info(f"Step 3: {len(candidates)} → {len(keyframes)} after SSIM")

        # Step 4: Debounce
        keyframes = _debounce(keyframes)
        logger.info(f"Step 4: → {len(keyframes)} after debounce")

        # Step 5: Global dedup
        keyframes = _global_dedup(keyframes)
        logger.info(f"Step 5: → {len(keyframes)} after global dedup")

        # Step 6: Replace blurry frames
        if status_callback:
            status_callback("Replacing blurry frames...")
        keyframes = _replace_blurry_frames(keyframes, video_url, output_dir, status_callback)

        # Copy final keyframes to output dir and build result
        results = []
        for path in keyframes:
            t = frame_to_seconds(path)
            dest = os.path.join(output_dir, f"frame_{t:05d}.jpg")
            shutil.copy2(path, dest)

            sharpness = laplacian_variance(dest)
            results.append(KeyframeInfo(
                path=dest,
                timestamp=t,
                timestamp_str=format_time(t),
                sharpness=sharpness,
                is_visual=sharpness >= VISUAL_SHARPNESS_THRESHOLD,
            ))

        logger.info(f"Final: {len(results)} keyframes ({sum(1 for r in results if r.is_visual)} visual)")
        return results

    finally:
        # Clean up temp frames
        if os.path.exists(frames_dir):
            shutil.rmtree(frames_dir)
