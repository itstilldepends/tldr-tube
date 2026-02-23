"""
Quick test script for export functionality.

This script tests the export functions without needing to run the full Streamlit app.
"""

import json
from datetime import datetime
from pipeline.export import export_video_to_markdown, export_collection_to_markdown


# Mock Video object
class MockVideo:
    def __init__(self):
        self.id = 1
        self.video_id = "test123"
        self.title = "Test Video: Python Programming"
        self.source_url = "https://www.youtube.com/watch?v=test123"
        self.channel_name = "Test Channel"
        self.duration_seconds = 1234
        self.upload_date = "2024-01-15"
        self.tags = json.dumps(["python", "programming", "tutorial"])
        self.video_type = "tutorial"
        self.transcript_source = "youtube_api"
        self.processed_at = datetime.now()
        self.description = "This is a test video description."
        self.tldr = "This video covers Python programming basics including variables, loops, and functions."
        self.tldr_zh = "本视频涵盖 Python 编程基础，包括变量、循环和函数。"


# Mock Segment object
class MockSegment:
    def __init__(self, start, end, timestamp, summary, summary_zh):
        self.start_seconds = start
        self.end_seconds = end
        self.timestamp = timestamp
        self.summary = summary
        self.summary_zh = summary_zh


# Mock Collection object
class MockCollection:
    def __init__(self):
        self.id = 1
        self.title = "Python Course"
        self.description = "A comprehensive Python course"
        self.created_at = datetime.now()


def test_video_export():
    """Test single video export to Markdown."""
    print("Testing video export to Markdown...")

    # Create mock data
    video = MockVideo()
    segments = [
        MockSegment(0, 120, "00:00", "Introduction to Python and setup.", "Python 和设置介绍。"),
        MockSegment(120, 300, "02:00", "Variables and data types explained.", "变量和数据类型说明。"),
        MockSegment(300, 500, "05:00", "Control flow: if statements and loops.", "控制流：if 语句和循环。"),
    ]

    # Test English export
    try:
        markdown_en = export_video_to_markdown(video, segments, language="en")
        print("\n✅ English export successful")
        print(f"Length: {len(markdown_en)} characters")
        print("\nFirst 500 characters:")
        print(markdown_en[:500])
    except Exception as e:
        print(f"\n❌ English export failed: {e}")

    # Test Chinese export
    try:
        markdown_zh = export_video_to_markdown(video, segments, language="zh")
        print("\n✅ Chinese export successful")
        print(f"Length: {len(markdown_zh)} characters")
        print("\nFirst 500 characters:")
        print(markdown_zh[:500])
    except Exception as e:
        print(f"\n❌ Chinese export failed: {e}")


def test_collection_export():
    """Test collection export to Markdown."""
    print("\n\nTesting collection export to Markdown...")

    # Create mock data
    collection = MockCollection()
    video1 = MockVideo()
    video1.title = "Lesson 1: Introduction"
    segments1 = [
        MockSegment(0, 120, "00:00", "Intro to course.", "课程介绍。"),
    ]

    video2 = MockVideo()
    video2.title = "Lesson 2: Advanced Topics"
    video2.video_id = "test456"
    video2.source_url = "https://www.youtube.com/watch?v=test456"
    segments2 = [
        MockSegment(0, 180, "00:00", "Deep dive into advanced topics.", "深入探讨高级主题。"),
    ]

    videos_with_segments = [
        (video1, segments1),
        (video2, segments2),
    ]

    # Test English export
    try:
        markdown_en = export_collection_to_markdown(collection, videos_with_segments, language="en")
        print("\n✅ Collection export (English) successful")
        print(f"Length: {len(markdown_en)} characters")
        print("\nFirst 500 characters:")
        print(markdown_en[:500])
    except Exception as e:
        print(f"\n❌ Collection export failed: {e}")


if __name__ == "__main__":
    print("="*60)
    print("Export Function Test")
    print("="*60)

    test_video_export()
    test_collection_export()

    print("\n" + "="*60)
    print("Test completed!")
    print("="*60)
