"""
Backfill embeddings for existing videos.

This script generates BGE-M3 embeddings for all videos that don't have them yet.
Safe to run multiple times - it only processes videos with embedding = NULL.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.session import get_session
from db.models import Video
from pipeline.embeddings import generate_video_embedding


def backfill_embeddings():
    """Generate embeddings for all videos without them."""

    print("="*60)
    print("Backfill Embeddings for Semantic Search")
    print("="*60)
    print()

    # Get videos without embeddings
    with get_session() as session:
        videos_without_embeddings = session.query(Video).filter(
            Video.embedding.is_(None)
        ).all()

        total_videos = session.query(Video).count()
        videos_with_embeddings = session.query(Video).filter(
            Video.embedding.isnot(None)
        ).count()

    print(f"📊 Current state:")
    print(f"   Total videos: {total_videos}")
    print(f"   Videos with embeddings: {videos_with_embeddings}")
    print(f"   Videos without embeddings: {len(videos_without_embeddings)}")
    print()

    if not videos_without_embeddings:
        print("✅ All videos already have embeddings!")
        print()
        return

    print(f"🔧 Processing {len(videos_without_embeddings)} video(s)...")
    print()

    # Process each video
    success_count = 0
    error_count = 0

    for i, video in enumerate(videos_without_embeddings, 1):
        print(f"[{i}/{len(videos_without_embeddings)}] Processing: {video.title[:50]}...")

        try:
            # Generate embedding
            embedding_bytes = generate_video_embedding(video)

            # Save to database
            with get_session() as session:
                video_to_update = session.query(Video).filter_by(id=video.id).first()
                video_to_update.embedding = embedding_bytes
                session.commit()

            print(f"  ✅ Embedding generated and saved")
            success_count += 1

        except Exception as e:
            print(f"  ❌ Error: {str(e)}")
            error_count += 1

        print()

    print("="*60)
    print("Backfill Complete!")
    print("="*60)
    print()
    print(f"📊 Results:")
    print(f"   ✅ Successfully processed: {success_count}")
    print(f"   ❌ Errors: {error_count}")
    print()

    if success_count > 0:
        print("🎉 Your videos now support semantic search!")
        print("   Try searching in the History view with natural language queries.")
        print()


if __name__ == "__main__":
    backfill_embeddings()
