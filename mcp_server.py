"""
MCP server for tldr-tube.

Exposes video processing, search, RAG Q&A, and library browsing as MCP tools
and resources so AI agents can interact with the tldr-tube pipeline.

Usage:
    # Install the entry point once (from the project root):
    pip install -e .

    # Then register in Claude Desktop (~/.claude/mcp_settings.json):
    {
      "mcpServers": {
        "tldr-tube": {
          "command": "tldr-tube-mcp"
        }
      }
    }

    # Or run directly without installing:
    python mcp_server.py

    # Interactive testing with MCP Inspector:
    mcp dev mcp_server.py
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Optional

from mcp.server.fastmcp import Context, FastMCP
from sqlalchemy.orm import joinedload

from db.models import Collection, Video
from db.operations import get_all_collections
from db.session import get_session, init_db
from pipeline.export import export_collection_to_markdown, export_video_to_markdown
from pipeline.processor import (
    get_all_videos,
    process_video as _process_video,
)
from pipeline.rag import answer_question
from pipeline.search import hybrid_search
from pipeline.utils import generate_timestamp_link


# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def _lifespan(server: FastMCP) -> AsyncIterator[None]:
    """Initialize the database on server startup."""
    init_db()
    yield


mcp = FastMCP("tldr-tube", lifespan=_lifespan)


# ---------------------------------------------------------------------------
# Serialization helpers
# All helpers that access ORM relationships must be called while the session
# is still open, or after joinedload has been used to pre-load them.
# ---------------------------------------------------------------------------

def _serialize_segment(seg, source_url: str, source_type: str) -> dict:
    """Convert a Segment ORM row to a plain dict (must be called in-session)."""
    return {
        "timestamp": seg.timestamp,
        "start_seconds": seg.start_seconds,
        "end_seconds": seg.end_seconds,
        "summary_en": seg.summary,
        "summary_zh": seg.summary_zh,
        "link": generate_timestamp_link(source_url, source_type, int(seg.start_seconds)),
    }


def _serialize_video(video: Video, include_segments: bool = False) -> dict:
    """
    Convert a Video ORM row to a plain dict.

    When include_segments=True, video.segments must already be loaded
    (either in-session or via joinedload).
    """
    data = {
        "id": video.id,
        "video_id": video.video_id,
        "title": video.title,
        "channel_name": video.channel_name,
        "duration_seconds": video.duration_seconds,
        "source_url": video.source_url,
        "source_type": video.source_type,
        "video_type": video.video_type,
        "transcript_source": video.transcript_source,
        "upload_date": video.upload_date,
        "thumbnail_url": video.thumbnail_url,
        "tldr_en": video.tldr,
        "tldr_zh": video.tldr_zh,
        "processed_at": video.processed_at.isoformat() if video.processed_at else None,
        "collection_id": video.collection_id,
    }
    if include_segments:
        data["segments"] = [
            _serialize_segment(seg, video.source_url, video.source_type)
            for seg in sorted(video.segments, key=lambda s: s.start_seconds)
        ]
    return data


def _serialize_collection_summary(col: Collection) -> dict:
    """
    Convert a Collection to a compact summary dict.

    col.videos must be eagerly loaded (get_all_collections uses joinedload).
    """
    return {
        "id": col.id,
        "title": col.title,
        "description": col.description,
        "video_count": len(col.videos),
        "created_at": col.created_at.isoformat() if col.created_at else None,
    }


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool(name="process_video")
async def process_video_tool(
    url: str,
    provider: str = "claude",
    model: Optional[str] = None,
    ctx: Context = None,
) -> dict:
    """
    Process a YouTube or Bilibili video URL through the full pipeline.

    Fetches the transcript, generates bilingual (EN + ZH) TL;DR and
    timestamped segment summaries using an LLM, and caches the result.
    Returns immediately for already-cached videos.

    Args:
        url: Full YouTube (youtube.com/watch?v=... or youtu.be/...) or Bilibili URL
        provider: LLM provider - "claude", "gemini", "openai", "deepseek",
                  "qwen", or "ollama". Defaults to "claude".
        model: Provider-specific model name (e.g. "sonnet", "flash").
               Omit to use the provider's default model.

    Returns:
        Video metadata, bilingual TL;DR, and list of timestamped segments.
    """
    progress_log: list[str] = []

    def _callback(step: str, status: str) -> None:
        prefix = {"running": "[...]", "success": "[OK ]", "error": "[ERR]"}.get(status, "[   ]")
        progress_log.append(f"{prefix} {step}")

    if ctx:
        await ctx.info(f"Starting pipeline for: {url}")

    try:
        video = await asyncio.to_thread(
            _process_video,
            url=url,
            status_callback=_callback,
            provider=provider,
            model=model,
        )
    except Exception as exc:
        if ctx:
            await ctx.info(f"Pipeline error: {exc}")
        raise

    if ctx:
        for msg in progress_log:
            await ctx.info(msg)

    # Re-fetch with segments eagerly loaded. The Video object returned by
    # _process_video is detached (its session closed), so video.segments
    # would raise DetachedInstanceError without a fresh joinedload.
    def _fetch_with_segments(video_id: int) -> dict:
        with get_session() as session:
            fresh = (
                session.query(Video)
                .options(joinedload(Video.segments))
                .filter_by(id=video_id)
                .first()
            )
            if fresh is None:
                raise RuntimeError(f"Video id={video_id} missing after processing")
            return _serialize_video(fresh, include_segments=True)

    result = await asyncio.to_thread(_fetch_with_segments, video.id)

    if ctx:
        await ctx.info(f"Done — {len(result.get('segments', []))} segments generated.")
    return result


@mcp.tool()
async def search_videos(
    query: str,
    top_k: int = 5,
    ctx: Context = None,
) -> list[dict]:
    """
    Search the video library using hybrid semantic + keyword matching.

    Combines BGE-M3 semantic embeddings with exact keyword matching.
    Supports queries in any language (EN or ZH).

    Args:
        query: Search query in any language
        top_k: Maximum number of results to return (default 5)

    Returns:
        List of matching videos with relevance scores. Empty if library is empty.
    """
    if ctx:
        await ctx.info(f"Searching: '{query}' (top_k={top_k})")

    results = await asyncio.to_thread(hybrid_search, query, top_k)

    output = []
    for video, score, match_info in results:
        # Video objects from hybrid_search are detached — scalar fields only.
        entry = _serialize_video(video, include_segments=False)
        entry["relevance_score"] = round(score, 4)
        entry["match_info"] = match_info
        output.append(entry)

    if ctx:
        await ctx.info(f"Found {len(output)} results.")
    return output


@mcp.tool()
async def ask_videos(
    question: str,
    language: str = "auto",
    provider: str = "claude",
    model: Optional[str] = None,
    ctx: Context = None,
) -> dict:
    """
    Ask a question and get an AI-generated answer from your video library.

    Uses RAG (Retrieval-Augmented Generation): finds relevant videos and
    segments, then synthesizes an answer with source citations and timestamps.

    Args:
        question: Natural language question (any language)
        language: Response language - "auto" (detect from question),
                  "en" (English), or "zh" (Chinese)
        provider: LLM provider for answer generation
        model: Provider-specific model name

    Returns:
        dict with 'answer' (Markdown with citations), 'status', and 'sources'.
    """
    if ctx:
        await ctx.info(f"RAG Q&A: '{question[:80]}'")

    lang = None if language == "auto" else language

    rag_result = await asyncio.to_thread(
        answer_question,
        question=question,
        provider=provider,
        model=model,
        language=lang,
    )

    sources = []
    for video, score, _match in rag_result.get("videos", []):
        entry = _serialize_video(video, include_segments=False)
        entry["relevance_score"] = round(score, 4)
        sources.append(entry)

    return {
        "status": rag_result["status"],
        "answer": rag_result["answer"],
        "sources": sources,
        # Omit "context" (large internal debug string)
    }


@mcp.tool()
async def list_videos(ctx: Context = None) -> list[dict]:
    """
    List all processed standalone videos (not in any collection).

    Returns:
        List of video metadata dicts ordered by most recently processed.
        Empty list if no videos have been processed yet.
    """
    videos = await asyncio.to_thread(get_all_videos)
    if ctx:
        await ctx.info(f"{len(videos)} standalone videos found.")
    # get_all_videos() returns detached objects; scalar fields are accessible.
    return [_serialize_video(v) for v in videos]


@mcp.tool()
async def list_collections(ctx: Context = None) -> list[dict]:
    """
    List all video collections with their video counts.

    Returns:
        List of collection summaries. Empty list if no collections exist.
    """
    cols = await asyncio.to_thread(get_all_collections)
    if ctx:
        await ctx.info(f"{len(cols)} collections found.")
    # get_all_collections() uses joinedload + expunge_all, so col.videos is safe.
    return [_serialize_collection_summary(c) for c in cols]


@mcp.tool()
async def get_video_segments(
    video_id: str,
    ctx: Context = None,
) -> dict:
    """
    Get all timestamped segments for a specific video.

    Args:
        video_id: YouTube video ID (e.g. "dQw4w9WgXcQ") or Bilibili BV ID.
                  Use the 'video_id' field from list_videos or search_videos.

    Returns:
        Video metadata with 'segments' list containing timestamps, bilingual
        summaries, and clickable timestamp links. Returns {'error': ...} if
        video not found.
    """
    if ctx:
        await ctx.info(f"Fetching segments for video_id={video_id}")

    def _fetch() -> Optional[dict]:
        with get_session() as session:
            video = (
                session.query(Video)
                .options(joinedload(Video.segments))
                .filter_by(video_id=video_id)
                .first()
            )
            if video is None:
                return None
            return _serialize_video(video, include_segments=True)

    result = await asyncio.to_thread(_fetch)

    if result is None:
        return {"error": f"Video not found: '{video_id}'. Use list_videos to see available IDs."}

    if ctx:
        await ctx.info(f"{len(result.get('segments', []))} segments returned.")
    return result


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

@mcp.resource("video:///{video_id}")
async def video_resource(video_id: str) -> str:
    """
    Full Markdown summary of a video (TL;DR + timestamped segments).

    URI format: video:///dQw4w9WgXcQ  (YouTube/Bilibili video_id)
    """
    def _fetch() -> Optional[str]:
        with get_session() as session:
            video = (
                session.query(Video)
                .options(joinedload(Video.segments))
                .filter_by(video_id=video_id)
                .first()
            )
            if video is None:
                return None
            segments = sorted(video.segments, key=lambda s: s.start_seconds)
            return export_video_to_markdown(video, segments, language="en")

    result = await asyncio.to_thread(_fetch)
    return result or f"# Video Not Found\n\nNo video with ID `{video_id}` in the library.\n"


@mcp.resource("collection:///{collection_id}")
async def collection_resource(collection_id: str) -> str:
    """
    Full Markdown overview of a collection (all videos with TL;DRs and timelines).

    URI format: collection:///1  (integer collection ID from list_collections)
    """
    def _fetch() -> Optional[str]:
        coll_id = int(collection_id)
        with get_session() as session:
            col = (
                session.query(Collection)
                .options(
                    joinedload(Collection.videos).joinedload(Video.segments)
                )
                .filter_by(id=coll_id)
                .first()
            )
            if col is None:
                return None
            videos_with_segs = [
                (v, sorted(v.segments, key=lambda s: s.start_seconds))
                for v in sorted(col.videos, key=lambda v: v.order_index or 0)
            ]
            return export_collection_to_markdown(col, videos_with_segs, language="en")

    try:
        result = await asyncio.to_thread(_fetch)
    except ValueError:
        return f"# Invalid ID\n\n`{collection_id}` must be an integer.\n"

    return result or f"# Collection Not Found\n\nNo collection with ID `{collection_id}` in the library.\n"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Entry point for the `tldr-tube-mcp` console script."""
    mcp.run()  # stdio transport — compatible with Claude Desktop and openclaw


if __name__ == "__main__":
    main()
