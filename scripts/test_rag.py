"""
Quick test for RAG functionality.

This script tests the RAG pipeline without the UI.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.rag import answer_question


def test_rag():
    """Test RAG with a simple question."""

    print("=" * 60)
    print("Testing RAG Q&A System")
    print("=" * 60)
    print()

    # Test question
    question = "What is OpenClaw?"

    print(f"Question: {question}")
    print()
    print("⏳ Searching and generating answer...")
    print()

    try:
        result = answer_question(
            question=question,
            top_k_videos=3,
            top_k_segments=3,
            model="sonnet",
            min_video_score=0.2  # Lower threshold for testing
        )

        print("=" * 60)
        print("RESULT")
        print("=" * 60)
        print()

        if result['status'] == 'no_results':
            print("❌ No relevant videos found")
            print(result['answer'])
        else:
            print("✅ Answer generated successfully!")
            print()
            print("📚 Videos used:", len(result['videos']))
            for i, (video, score, match_info) in enumerate(result['videos'], 1):
                print(f"  {i}. {video.title} ({match_info}, score: {score:.3f})")
            print()
            print("-" * 60)
            print("ANSWER:")
            print("-" * 60)
            print(result['answer'])
            print()

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_rag()
