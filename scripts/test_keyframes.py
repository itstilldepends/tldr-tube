"""
Test script for keyframe extraction pipeline.

Usage:
    python scripts/test_keyframes.py <deeplearning_ai_lesson_url>

Outputs:
    data/keyframe_test/{video_id}/          — keyframe images
    data/keyframe_test/{video_id}/report.html — visual report for review
"""

import sys
import os
import json
import re
import subprocess
import shutil
import time
from pathlib import Path

import requests
import imagehash
from PIL import Image
import cv2
from skimage.metrics import structural_similarity as ssim


# ── Step 0: Fetch video URL from DeepLearning.AI page ──────────────────────

def fetch_video_info(url: str) -> dict:
    """Extract video stream URL, title, and duration from a DeepLearning.AI lesson page."""
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()

    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', resp.text, re.DOTALL)
    if not match:
        raise Exception("Could not find __NEXT_DATA__ in page")

    data = json.loads(match.group(1))
    trpc_state = data["props"]["pageProps"]["trpcState"]

    video_data = None
    course_data = None
    lesson_slug = data["props"]["pageProps"].get("lessonId", "")

    for query in trpc_state.get("json", {}).get("queries", []):
        key = query.get("queryKey", [])
        if key and isinstance(key[0], list):
            if "getLessonVideo" in key[0] and "getLessonVideoSubtitle" not in key[0]:
                video_data = query["state"]["data"]["video"]
            if "getCourseBySlug" in key[0]:
                course_data = query["state"]["data"]

    if not video_data:
        raise Exception("Could not find video data in page")

    # Get lesson name from course data
    lesson_name = lesson_slug
    if course_data and lesson_slug:
        lessons = course_data.get("lessons", {})
        lesson_info = lessons.get(lesson_slug, {})
        lesson_name = lesson_info.get("name", lesson_slug)

    course_name = course_data.get("name", "") if course_data else ""
    title = f"{course_name} - {lesson_name}" if course_name else lesson_name

    return {
        "video_id": lesson_slug,
        "title": title,
        "hls_url": video_data["mp4Url"],  # actually m3u8
        "mp4_360p_url": video_data.get("mp4360pUrl", ""),
    }


# ── Step 1: Extract frames at 1fps ─────────────────────────────────────────

def extract_frames(video_url: str, output_dir: str) -> list[str]:
    """Extract frames at 1fps using ffmpeg from HLS stream."""
    os.makedirs(output_dir, exist_ok=True)

    cmd = [
        "ffmpeg", "-i", video_url,
        "-vf", "fps=1,scale=1280:-1",
        "-q:v", "3",
        os.path.join(output_dir, "frame_%05d.jpg"),
        "-y", "-loglevel", "warning"
    ]

    print(f"  Extracting frames from video...")
    start = time.time()
    subprocess.run(cmd, check=True)
    elapsed = time.time() - start

    frames = sorted(
        [os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.startswith("frame_")],
    )
    print(f"  Extracted {len(frames)} frames in {elapsed:.1f}s")
    return frames


def frame_to_seconds(path: str) -> int:
    """Extract timestamp from frame filename. frame_00001.jpg → 0 (0-indexed)."""
    name = os.path.basename(path)
    num = int(re.search(r"(\d+)", name).group(1))
    return num - 1  # ffmpeg starts at 00001


# ── Step 1.5: Filter dark/black frames ──────────────────────────────────────

def filter_dark_frames(frame_paths: list[str], brightness_threshold: int = 15) -> list[str]:
    """Remove near-black frames (intro/outro/transitions)."""
    result = []
    for path in frame_paths:
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if img is not None and img.mean() > brightness_threshold:
            result.append(path)
    return result


# ── Step 2: pHash coarse filter ─────────────────────────────────────────────

def coarse_filter(frame_paths: list[str], threshold: int = 5) -> list[str]:
    """Keep the LAST frame of each stable period.

    Compares each frame to its immediate predecessor (consecutive comparison).
    When a big change is detected at frame N, frame N-1 is the "final state"
    of the previous slide. This captures complete slides, not partial builds.

    For gradual changes (PPT adding bullets one by one), each step is small
    and doesn't trigger the threshold — the whole build-up is treated as one
    stable period, and we keep the final (complete) frame.
    """
    if not frame_paths:
        return []

    prev_hash = imagehash.phash(Image.open(frame_paths[0]))
    segment_last = frame_paths[0]
    candidates = []

    for path in frame_paths[1:]:
        h = imagehash.phash(Image.open(path))
        if prev_hash - h >= threshold:
            # Transition detected — save the last frame of previous segment
            candidates.append(segment_last)
        segment_last = path
        prev_hash = h

    # Always keep the last frame (final segment's end)
    candidates.append(segment_last)
    return candidates


# ── Step 3: SSIM fine filter ────────────────────────────────────────────────

def fine_filter(candidates: list[str], threshold: float = 0.85) -> list[str]:
    """Remove pHash false positives using SSIM.

    pHash may flag frames as different when they're visually near-identical
    (e.g. compression artifacts, lighting shifts). SSIM compares local
    luminance/contrast/structure and is more aligned with human perception.

    Compares each candidate to its predecessor. If SSIM is high (frames look
    the same despite pHash saying different), drop the older one and keep the
    newer one as the representative.
    """
    if not candidates:
        return []

    keyframes = [candidates[0]]
    prev = cv2.imread(candidates[0], cv2.IMREAD_GRAYSCALE)
    prev = cv2.resize(prev, (640, 360))

    for path in candidates[1:]:
        curr = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        curr = cv2.resize(curr, (640, 360))
        score, _ = ssim(prev, curr, full=True)
        if score >= threshold:
            # Too similar — pHash false positive, replace with newer frame
            keyframes[-1] = path
        else:
            # Genuinely different — keep both
            keyframes.append(path)
        prev = curr

    return keyframes


# ── Step 4: Debounce ────────────────────────────────────────────────────────

def debounce(keyframe_paths: list[str], window: int = 4) -> list[str]:
    """Keep the last frame in each burst within `window` seconds."""
    if not keyframe_paths:
        return []

    times = [frame_to_seconds(p) for p in keyframe_paths]
    path_by_time = dict(zip(times, keyframe_paths))

    result_times = []
    i = 0
    while i < len(times):
        j = i
        while j < len(times) - 1 and times[j + 1] - times[i] < window:
            j += 1
        result_times.append(times[j])
        i = j + 1

    return [path_by_time[t] for t in result_times]


# ── Step 5: Global dedup ───────────────────────────────────────────────────

def global_dedup(keyframe_paths: list[str], threshold: int = 12) -> list[str]:
    """Remove globally duplicate slides (e.g., recurring agenda slide)."""
    if not keyframe_paths:
        return []

    hashes = [(p, imagehash.phash(Image.open(p))) for p in keyframe_paths]
    seen: list[tuple[str, imagehash.ImageHash]] = []

    for path, h in hashes:
        if not any(h - seen_h < threshold for _, seen_h in seen):
            seen.append((path, h))

    return [p for p, _ in seen]


# ── Step 6: Deblur (replace blurry keyframes) ──────────────────────────────

def laplacian_variance(path: str) -> float:
    """Compute Laplacian variance as a sharpness score. Higher = sharper."""
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    return cv2.Laplacian(img, cv2.CV_64F).var()


def sample_sharp_replacement(
    video_url: str,
    timestamp: float,
    output_dir: str,
    radius: float = 1.0,
    sample_fps: int = 10,
) -> tuple[str, float]:
    """Sample frames from video around timestamp and return the sharpest one.

    Extracts frames at sample_fps within [timestamp-radius, timestamp+radius]
    directly from the video source (not from existing 1fps frames).

    Returns (path_to_sharpest, sharpness_score).
    """
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
    subprocess.run(cmd, check=True)

    # Find sharpest among sampled frames
    best_path = None
    best_score = -1
    for f in os.listdir(tmp_dir):
        if not f.endswith(".jpg"):
            continue
        p = os.path.join(tmp_dir, f)
        s = laplacian_variance(p)
        if s > best_score:
            best_score = s
            best_path = p

    return best_path, best_score


def replace_blurry_frames(
    keyframe_paths: list[str],
    video_url: str,
    output_dir: str,
    abs_threshold: float = 300.0,
    rel_threshold: float = 0.85,
) -> tuple[list[str], int]:
    """Replace blurry keyframes with the sharpest nearby frame.

    A frame is considered blurry if EITHER:
    - Absolute: sharpness < abs_threshold (catches universally blurry frames)
    - Relative: sharpness < rel_threshold * median of neighbors (catches
      frames that are blurry relative to surrounding content, e.g. a
      transition frame between sharp PPT slides)

    For each blurry frame, samples at 10fps within ±1s directly from the
    video and picks the sharpest replacement.

    Returns (updated_paths, replacement_count).
    """
    # Pre-compute all sharpness scores
    scores = [laplacian_variance(p) for p in keyframe_paths]

    replaced = 0
    result = []

    for i, (path, score) in enumerate(zip(keyframe_paths, scores)):
        # Compute neighbor median (up to 2 neighbors on each side)
        neighbors = []
        for j in range(max(0, i - 2), min(len(scores), i + 3)):
            if j != i:
                neighbors.append(scores[j])
        neighbor_median = sorted(neighbors)[len(neighbors) // 2] if neighbors else score

        is_abs_blurry = score < abs_threshold
        is_rel_blurry = neighbor_median > 0 and score < rel_threshold * neighbor_median

        if not is_abs_blurry and not is_rel_blurry:
            result.append(path)
            continue

        reason = "absolute" if is_abs_blurry else f"relative ({score:.0f} vs neighbor median {neighbor_median:.0f})"
        t = frame_to_seconds(path)
        print(f"    Blurry frame at {format_time(t)} (sharpness={score:.0f}, {reason}), sampling ±1s at 10fps...")

        best_path, best_score = sample_sharp_replacement(
            video_url, float(t), output_dir,
            radius=1.0, sample_fps=10,
        )

        if best_path and best_score > score:
            shutil.copy2(best_path, path)
            replaced += 1
            print(f"    → Replaced with sharpness={best_score:.0f}")
        else:
            print(f"    → No better frame found, keeping original")

        # Clean up temp samples
        tmp_dir = os.path.join(output_dir, f"_blur_sample_{t}")
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)

        result.append(path)

    return result, replaced


# ── HTML Report ─────────────────────────────────────────────────────────────

def format_time(seconds: int) -> str:
    """Format seconds as MM:SS."""
    m, s = divmod(seconds, 60)
    return f"{m:02d}:{s:02d}"


def generate_report(
    title: str,
    keyframe_paths: list[str],
    stats: dict,
    output_path: str,
):
    """Generate an HTML report with all keyframes for visual inspection."""
    rows = []
    for i, path in enumerate(keyframe_paths):
        t = frame_to_seconds(path)
        filename = os.path.basename(path)
        score = laplacian_variance(path)
        if score < 600:
            badge = ' <span class="talk-badge">TALKING HEAD?</span>'
            border_style = "border: 3px solid #f66;"
        else:
            badge = ""
            border_style = "border: 1px solid #333;"
        rows.append(f"""
        <div class="keyframe">
            <div class="meta">#{i+1} &mdash; {format_time(t)} ({t}s) &mdash; sharpness: {score:.0f}{badge}</div>
            <img src="{filename}" alt="Keyframe at {format_time(t)}" style="{border_style}">
        </div>
        """)

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Keyframe Test: {title}</title>
<style>
    body {{ font-family: -apple-system, sans-serif; max-width: 1400px; margin: 0 auto; padding: 20px; background: #1a1a1a; color: #eee; }}
    h1 {{ font-size: 1.3em; }}
    .stats {{ background: #2a2a2a; padding: 12px 16px; border-radius: 8px; margin-bottom: 20px; font-size: 0.9em; line-height: 1.8; }}
    .stats span {{ color: #6cf; font-weight: bold; }}
    .keyframe {{ margin-bottom: 24px; }}
    .meta {{ font-size: 0.85em; color: #aaa; margin-bottom: 4px; }}
    .talk-badge {{ color: #f66; font-weight: bold; }}
    img {{ max-width: 100%; border: 1px solid #333; border-radius: 4px; }}
</style>
</head>
<body>
<h1>{title}</h1>
<div class="stats">
    Total frames extracted: <span>{stats['total_frames']}</span><br>
    After dark frame filter: <span>{stats['after_dark_filter']}</span><br>
    After pHash coarse filter: <span>{stats['after_phash']}</span><br>
    After SSIM fine filter: <span>{stats['after_ssim']}</span><br>
    After debounce (4s): <span>{stats['after_debounce']}</span><br>
    After global dedup: <span>{stats['after_dedup']}</span> (final)<br>
    Blurry frames replaced: <span>{stats['blur_replaced']}</span><br>
    Visual frames (img+text to LLM): <span>{stats['visual_frames']}</span> | Talking head (text only): <span style="color:#f66">{stats['talk_frames']}</span>
</div>
{''.join(rows)}
</body>
</html>"""

    with open(output_path, "w") as f:
        f.write(html)


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_keyframes.py <deeplearning_ai_lesson_url>")
        sys.exit(1)

    url = sys.argv[1]
    print(f"Fetching video info from: {url}")
    info = fetch_video_info(url)
    print(f"  Title: {info['title']}")
    print(f"  Video ID: {info['video_id']}")

    video_id = info["video_id"]
    base_dir = f"data/keyframe_test/{video_id}"
    frames_dir = f"{base_dir}/all_frames"
    keyframes_dir = base_dir

    # Step 1: Extract frames
    print("\n[Step 1] Extracting frames at 1fps...")
    all_frames = extract_frames(info["hls_url"], frames_dir)
    total = len(all_frames)

    # Step 1.5: Filter dark frames
    print(f"\n[Step 1.5] Filtering dark/black frames...")
    bright_frames = filter_dark_frames(all_frames, brightness_threshold=15)
    print(f"  {total} → {len(bright_frames)} (removed {total - len(bright_frames)} dark frames)")

    # Step 2: pHash coarse filter
    print(f"\n[Step 2] pHash coarse filter (threshold=5)...")
    candidates = coarse_filter(bright_frames, threshold=5)
    print(f"  {len(bright_frames)} → {len(candidates)} candidates")

    # Step 3: SSIM fine filter
    print(f"\n[Step 3] SSIM fine filter (threshold=0.85)...")
    keyframes = fine_filter(candidates, threshold=0.85)
    after_ssim = len(keyframes)
    print(f"  {len(candidates)} → {after_ssim} keyframes")

    # Step 4: Debounce
    print(f"\n[Step 4] Debounce (window=4s)...")
    keyframes = debounce(keyframes, window=4)
    after_debounce = len(keyframes)
    print(f"  → {after_debounce} after debounce")

    # Step 5: Global dedup
    print(f"\n[Step 5] Global dedup (threshold=12)...")
    keyframes = global_dedup(keyframes, threshold=12)
    print(f"  → {len(keyframes)} after dedup")

    # Step 6: Replace blurry keyframes
    print(f"\n[Step 6] Checking for blurry frames (Laplacian variance)...")
    keyframes, blur_replaced = replace_blurry_frames(
        keyframes, info["hls_url"], keyframes_dir,
    )
    print(f"  Replaced {blur_replaced} blurry frame(s) with sharper nearby alternatives")

    # Copy final keyframes to output dir (not inside all_frames)
    final_paths = []
    for path in keyframes:
        t = frame_to_seconds(path)
        dest = os.path.join(keyframes_dir, f"frame_{t:05d}.jpg")
        shutil.copy2(path, dest)
        final_paths.append(dest)

    # Stats for report
    stats = {
        "total_frames": total,
        "after_dark_filter": len(bright_frames),
        "after_phash": len(candidates),
        "after_ssim": after_ssim,
        "after_debounce": after_debounce,
        "after_dedup": len(keyframes),
        "blur_replaced": blur_replaced,
        "visual_frames": sum(1 for p in final_paths if laplacian_variance(p) >= 600),
        "talk_frames": sum(1 for p in final_paths if laplacian_variance(p) < 600),
    }

    # Generate HTML report
    report_path = os.path.join(keyframes_dir, "report.html")
    generate_report(info["title"], final_paths, stats, report_path)

    # Clean up all_frames to save space
    shutil.rmtree(frames_dir)

    print(f"\n{'='*50}")
    print(f"Done! {len(keyframes)} keyframes extracted.")
    print(f"Report: {report_path}")
    print(f"Open with: open {report_path}")


if __name__ == "__main__":
    main()
