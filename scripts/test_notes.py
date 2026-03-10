"""
End-to-end test for concept-based keyframe note generation.

Usage:
    python scripts/test_notes.py <deeplearning_ai_lesson_url>

Requires the video to already be processed in the DB (has transcript + segments).
If not, process it first via the app or MCP server.

Outputs:
    data/keyframe_test/{video_id}/notes_report.html
"""

import sys
import os
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from db.session import get_session
from db.models import Video, Segment
from sqlalchemy.orm import joinedload
from pipeline.keyframes import extract_keyframes, get_deeplearning_video_url
from pipeline.keyframe_notes import generate_keyframe_notes, ConceptNote
from pipeline.utils import extract_deeplearning_id


def fetch_video_from_db(video_id: str) -> tuple:
    """Fetch video with segments from DB."""
    with get_session() as session:
        video = session.query(Video).options(
            joinedload(Video.segments)
        ).filter_by(video_id=video_id).first()

        if not video:
            return None, None, None, None, None

        transcript = json.loads(video.raw_transcript)
        segments = [
            {
                "start_seconds": s.start_seconds,
                "end_seconds": s.end_seconds,
                "summary": s.summary,
            }
            for s in sorted(video.segments, key=lambda s: s.start_seconds)
        ]
        return video.title, transcript, segments, video.tldr, video.duration_seconds


def generate_notes_report(
    title: str,
    notes: list[ConceptNote],
    output_path: str,
):
    """Generate HTML report with concept-based notes and keyframe images."""
    sections = []
    for i, note in enumerate(notes):
        # Build image gallery for this concept
        images_html = ""
        for kf in note.keyframes:
            filename = os.path.basename(kf.path)
            images_html += f"""
            <div class="kf-thumb">
                <img src="{filename}" alt="Keyframe at {kf.timestamp_str}">
                <div class="kf-time">{kf.timestamp_str}</div>
            </div>
            """

        zh_title = f' <span class="zh-title">/ {note.title_zh}</span>' if note.title_zh else ""
        zh_notes = f'<div class="concept-notes zh">{note.notes_zh}</div>' if note.notes_zh else ""

        sections.append(f"""
        <div class="concept">
            <div class="concept-title">{note.title}{zh_title}</div>
            <div class="concept-body">
                <div class="kf-gallery">{images_html}</div>
                <div class="notes-columns">
                    <div class="concept-notes en">{note.notes}</div>
                    {zh_notes}
                </div>
            </div>
        </div>
        """)

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Notes: {title}</title>
<style>
    body {{ font-family: -apple-system, sans-serif; max-width: 1400px; margin: 0 auto; padding: 20px; background: #1a1a1a; color: #eee; }}
    h1 {{ font-size: 1.3em; }}
    .summary {{ background: #2a2a2a; padding: 12px 16px; border-radius: 8px; margin-bottom: 24px; font-size: 0.9em; }}
    .concept {{ margin-bottom: 32px; border: 1px solid #333; border-radius: 8px; overflow: hidden; }}
    .concept-title {{ background: #2a2a2a; padding: 12px 16px; font-size: 1.1em; font-weight: bold; color: #6cf; }}
    .concept-body {{ padding: 16px; }}
    .kf-gallery {{ display: flex; gap: 12px; margin-bottom: 16px; overflow-x: auto; }}
    .kf-thumb {{ flex-shrink: 0; }}
    .kf-thumb img {{ width: 320px; border: 1px solid #444; border-radius: 4px; }}
    .kf-time {{ text-align: center; font-size: 0.8em; color: #888; margin-top: 4px; }}
    .notes-columns {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }}
    .concept-notes {{ line-height: 1.7; white-space: pre-wrap; }}
    .concept-notes.zh {{ color: #aaa; }}
    .zh-title {{ color: #aaa; font-weight: normal; font-size: 0.9em; }}
</style>
</head>
<body>
<h1>{title}</h1>
<div class="summary">
    Topics: <strong>{len(notes)}</strong> |
    Keyframes referenced: <strong>{sum(len(n.keyframes) for n in notes)}</strong>
</div>
{''.join(sections)}
</body>
</html>"""

    with open(output_path, "w") as f:
        f.write(html)


def run_notes(url, video_id, title, transcript, segments, tldr, duration, keyframes, output_dir, merge_batches=True):
    """Run note generation with given batch strategy and produce report."""
    label = "merged" if merge_batches else "per-section"
    print(f"\n[Phase 2] Generating notes ({label})...")
    notes = generate_keyframe_notes(
        keyframes=keyframes,
        transcript=transcript,
        video_duration=duration,
        tldr=tldr,
        segments=segments,
        merge_batches=merge_batches,
        status_callback=lambda msg: print(f"  {msg}")
    )
    print(f"  → {len(notes)} concept notes generated")
    for note in notes:
        print(f"    - {note.title} ({len(note.keyframes)} keyframes)")

    report_path = os.path.join(output_dir, f"notes_{label}.html")
    generate_notes_report(f"{title} [{label}]", notes, report_path)
    return report_path


def main():
    # Parse args
    compare = "--compare" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    if not args:
        print("Usage: python scripts/test_notes.py <deeplearning_ai_lesson_url> [--compare]")
        print("  --compare  Generate both merged and per-section reports for comparison")
        sys.exit(1)

    url = args[0]
    video_id = extract_deeplearning_id(url)
    print(f"Video ID: {video_id}")

    # Fetch from DB
    print("Fetching video data from DB...")
    title, transcript, segments, tldr, duration = fetch_video_from_db(video_id)
    if not title:
        print(f"Video {video_id} not found in DB. Process it first via the app.")
        sys.exit(1)

    print(f"  Title: {title}")
    print(f"  Duration: {duration}s")
    print(f"  Transcript entries: {len(transcript)}")
    print(f"  Segments: {len(segments)}")

    # Get video URL
    print("\nFetching video stream URL...")
    video_url = get_deeplearning_video_url(url)

    # Extract keyframes
    output_dir = f"data/keyframe_test/{video_id}"
    print("\n[Phase 1] Extracting keyframes...")
    keyframes = extract_keyframes(
        video_url, output_dir,
        status_callback=lambda msg: print(f"  {msg}")
    )
    print(f"  → {len(keyframes)} keyframes ({sum(1 for k in keyframes if k.is_visual)} visual)")

    if compare:
        # Run both strategies on same keyframes
        report1 = run_notes(url, video_id, title, transcript, segments, tldr, duration, keyframes, output_dir, merge_batches=True)
        report2 = run_notes(url, video_id, title, transcript, segments, tldr, duration, keyframes, output_dir, merge_batches=False)
        print(f"\n{'='*50}")
        print(f"Comparison reports:")
        print(f"  Merged:      {report1}")
        print(f"  Per-section: {report2}")
        print(f"Open both: open {report1} {report2}")
    else:
        report_path = run_notes(url, video_id, title, transcript, segments, tldr, duration, keyframes, output_dir, merge_batches=True)
        print(f"\n{'='*50}")
        print(f"Done! Notes report: {report_path}")
        print(f"Open with: open {report_path}")


if __name__ == "__main__":
    main()
