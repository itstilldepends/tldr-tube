"""
Export video summaries to various formats (Markdown, PDF).

Functions:
- export_video_to_markdown: Export single video to Markdown format
- export_collection_to_markdown: Export entire collection to Markdown format
- export_video_to_pdf: Export single video to PDF format (future)
"""

import json
from datetime import datetime
from typing import List
from db.models import Video, Segment, Collection
from pipeline.utils import format_timestamp


def export_video_to_markdown(video: Video, segments: List[Segment], language: str = "en") -> str:
    """
    Export a video summary to Markdown format.

    Args:
        video: Video object from database
        segments: List of Segment objects for the video
        language: "en" for English, "zh" for Chinese

    Returns:
        Markdown-formatted string
    """
    # Choose language-specific content
    if language == "zh":
        tldr = video.tldr_zh
        summary_field = "summary_zh"
        header_tldr = "📝 概要"
        header_timeline = "🕒 时间线"
        label_channel = "频道"
        label_duration = "时长"
        label_upload = "上传日期"
        label_type = "类型"
        label_source = "转录来源"
        label_processed = "处理日期"
        label_tags = "标签"
        label_to = "至"
    else:
        tldr = video.tldr
        summary_field = "summary"
        header_tldr = "📝 TL;DR"
        header_timeline = "🕒 Timeline"
        label_channel = "Channel"
        label_duration = "Duration"
        label_upload = "Upload Date"
        label_type = "Type"
        label_source = "Transcript Source"
        label_processed = "Processed Date"
        label_tags = "Tags"
        label_to = "to"

    # Build markdown content
    lines = []

    # Title
    lines.append(f"# {video.title}\n")

    # Video URL
    lines.append(f"**Video URL**: {video.source_url}\n")

    # Metadata
    lines.append("## 📊 Metadata\n")
    lines.append(f"- **{label_channel}**: {video.channel_name}")

    if video.duration_seconds:
        duration_min = video.duration_seconds // 60
        duration_sec = video.duration_seconds % 60
        lines.append(f"- **{label_duration}**: {duration_min}:{duration_sec:02d}")

    if video.upload_date:
        lines.append(f"- **{label_upload}**: {video.upload_date}")

    lines.append(f"- **{label_type}**: {video.video_type}")
    lines.append(f"- **{label_source}**: {video.transcript_source}")

    if video.processed_at:
        processed_date = video.processed_at.strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"- **{label_processed}**: {processed_date}")

    # Tags
    if video.tags:
        try:
            tags_list = json.loads(video.tags)
            if tags_list:
                tags_str = ", ".join([f"`{tag}`" for tag in tags_list[:20]])  # First 20 tags
                lines.append(f"- **{label_tags}**: {tags_str}")
        except:
            pass

    lines.append("")  # Empty line

    # TL;DR
    lines.append(f"## {header_tldr}\n")
    lines.append(f"{tldr}\n")

    # Timeline
    lines.append(f"## {header_timeline}\n")

    for segment in segments:
        # Format timestamps
        start_time = segment.timestamp
        end_min = int(segment.end_seconds // 60)
        end_sec = int(segment.end_seconds % 60)
        end_time = f"{end_min:02d}:{end_sec:02d}"

        # YouTube link with timestamp
        youtube_link = f"{video.source_url}&t={int(segment.start_seconds)}s"

        # Get summary in the right language
        summary = getattr(segment, summary_field)

        # Add segment
        lines.append(f"### [{start_time}]({youtube_link}) - {label_to} {end_time}\n")
        lines.append(f"{summary}\n")

    # Footer
    lines.append("---")
    lines.append(f"\n*Exported from tldr-tube on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

    return "\n".join(lines)


def export_collection_to_markdown(collection: Collection, videos_with_segments: List[tuple], language: str = "en") -> str:
    """
    Export an entire collection to Markdown format.

    Args:
        collection: Collection object from database
        videos_with_segments: List of (Video, List[Segment]) tuples
        language: "en" for English, "zh" for Chinese

    Returns:
        Markdown-formatted string
    """
    # Choose language-specific content
    if language == "zh":
        header_collection = "📚 合集"
        label_description = "描述"
        label_created = "创建日期"
        label_video_count = "视频数量"
        label_video = "视频"
    else:
        header_collection = "📚 Collection"
        label_description = "Description"
        label_created = "Created Date"
        label_video_count = "Video Count"
        label_video = "Video"

    lines = []

    # Collection title
    lines.append(f"# {header_collection}: {collection.title}\n")

    # Collection metadata
    if collection.description:
        lines.append(f"**{label_description}**: {collection.description}\n")

    lines.append(f"**{label_created}**: {collection.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**{label_video_count}**: {len(videos_with_segments)}\n")

    lines.append("---\n")

    # Export each video
    for idx, (video, segments) in enumerate(videos_with_segments, start=1):
        lines.append(f"## {label_video} {idx}: {video.title}\n")

        # Video URL
        lines.append(f"**Video URL**: {video.source_url}\n")

        # TL;DR
        if language == "zh":
            tldr = video.tldr_zh
            summary_field = "summary_zh"
            header_tldr = "概要"
            header_timeline = "时间线"
        else:
            tldr = video.tldr
            summary_field = "summary"
            header_tldr = "TL;DR"
            header_timeline = "Timeline"

        lines.append(f"### {header_tldr}\n")
        lines.append(f"{tldr}\n")

        # Timeline (segments)
        lines.append(f"### {header_timeline}\n")

        for segment in segments:
            youtube_link = f"{video.source_url}&t={int(segment.start_seconds)}s"
            summary = getattr(segment, summary_field)
            lines.append(f"- **[{segment.timestamp}]({youtube_link})**: {summary}")

        lines.append("\n---\n")

    # Footer
    lines.append(f"\n*Exported from tldr-tube on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

    return "\n".join(lines)


def export_video_to_pdf(video: Video, segments: List[Segment], language: str = "en") -> bytes:
    """
    Export a video summary to PDF format.

    Args:
        video: Video object from database
        segments: List of Segment objects for the video
        language: "en" for English, "zh" for Chinese

    Returns:
        PDF file content as bytes

    Note:
        This is a placeholder for future implementation.
        Requires libraries like reportlab or weasyprint.
    """
    raise NotImplementedError(
        "PDF export is not yet implemented. "
        "Please use Markdown export instead, or convert Markdown to PDF manually."
    )
