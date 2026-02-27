"""
Quick test for RAG functionality with video filtering.

This script tests the RAG pipeline without the UI, including the new
filter_video_ids feature.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.rag import answer_question
from db.session import get_session
from db.models import Video


def test_rag():
    """Test RAG with a simple question."""

    print("=" * 80)
    print("Testing RAG Q&A System with Video Filtering")
    print("=" * 80)
    print()

    # Test question
    question = "What is OpenClaw?"

    print(f"Question: {question}")
    print()

    # Get all videos
    with get_session() as session:
        all_videos = session.query(Video).all()
        print(f"📚 Total videos in database: {len(all_videos)}")
        for i, video in enumerate(all_videos, 1):
            print(f"  {i}. {video.title[:70]}... (ID: {video.id})")
        print()

    # Test 1: Search all videos (no filter)
    print("=" * 80)
    print("TEST 1: Search ALL videos (no filter)")
    print("=" * 80)
    print()
    print("⏳ Searching and generating answer...")
    print()

    try:
        result = answer_question(
            question=question,
            top_k_videos=3,
            top_k_segments=3,
            model="sonnet",
            min_video_score=0.2,
            filter_video_ids=None  # No filter - search all videos
        )

        print_result(result, "All Videos")

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

    # Test 2: Filter to specific videos (if we have OpenClaw videos)
    openclaw_videos = [v for v in all_videos if "OpenClaw" in v.title or "Claw" in v.title]

    if len(openclaw_videos) > 0:
        print()
        print("=" * 80)
        print("TEST 2: Search ONLY OpenClaw videos (filtered)")
        print("=" * 80)
        print()
        print(f"🎯 Filter: Only searching in {len(openclaw_videos)} video(s)")
        for v in openclaw_videos:
            print(f"  - {v.title[:70]}... (ID: {v.id})")
        print()
        print("⏳ Searching and generating answer...")
        print()

        try:
            result2 = answer_question(
                question=question,
                top_k_videos=3,
                top_k_segments=3,
                model="sonnet",
                min_video_score=0.2,
                filter_video_ids=[v.id for v in openclaw_videos]  # Filtered
            )

            print_result(result2, "OpenClaw Videos Only")

        except Exception as e:
            print(f"❌ Error: {str(e)}")
            import traceback
            traceback.print_exc()
    else:
        print()
        print("⚠️  No OpenClaw videos found, skipping Test 2")

    print()
    print("=" * 80)
    print("✅ Tests completed!")
    print("=" * 80)


def print_result(result, test_name):
    """Print result in a formatted way."""
    print("=" * 80)
    print(f"RESULT: {test_name}")
    print("=" * 80)
    print()

    if result['status'] == 'no_results':
        print("❌ No relevant videos found")
        print(result['answer'])
    else:
        print("✅ Answer generated successfully!")
        print()
        print(f"📚 Videos used: {len(result['videos'])}")
        for i, (video, score, match_info) in enumerate(result['videos'], 1):
            print(f"  {i}. {video.title[:70]}...")
            print(f"     Match: {match_info}, Score: {score:.3f}")
        print()
        print("-" * 80)
        print("ANSWER:")
        print("-" * 80)
        print(result['answer'])
        print()


if __name__ == "__main__":
    test_rag()
