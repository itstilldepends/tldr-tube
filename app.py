"""
tldr-tube - Streamlit Web App

YouTube video summarizer with timestamp-anchored summaries.
"""

import os
import json
import streamlit as st
from dotenv import load_dotenv

from db.session import init_db, get_session
from db.models import Video, Segment, Collection
from db.operations import (
    create_collection, add_video_to_collection, remove_video_from_collection,
    move_video_in_collection, delete_collection, get_all_collections
)
from pipeline.processor import process_youtube_video, get_all_videos, delete_video
from pipeline.utils import validate_youtube_url, extract_video_id, format_timestamp
from pipeline.config import WHISPER_MODELS, CLAUDE_MODELS
from pipeline.export import export_video_to_markdown, export_collection_to_markdown

# Load environment variables
load_dotenv()

# Page config
st.set_page_config(
    page_title="tldr-tube",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)


def check_password():
    """
    Check if user has entered correct password.

    Returns:
        True if password is correct or not set, False otherwise
    """
    app_password = os.getenv("APP_PASSWORD")

    # If no password set, allow access
    if not app_password:
        return True

    # Check if password already verified in session
    if st.session_state.get("password_correct", False):
        return True

    # Show password input
    st.title("🔒 tldr-tube")
    st.markdown("### Enter password to access")

    password_input = st.text_input("Password", type="password", key="password_input")

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("Enter", type="primary"):
            if password_input == app_password:
                st.session_state.password_correct = True
                st.rerun()
            else:
                st.error("❌ Incorrect password")

    st.caption("Set APP_PASSWORD in .env file")

    return False


def render_video_result(video: Video):
    """
    Render a processed video's summary and segments.

    Args:
        video: Video object from database
    """
    # Header with metadata
    st.markdown(f"## 🎬 {video.title}")

    # Basic metadata row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.caption(f"📺 {video.channel_name}")
    with col2:
        if video.upload_date:
            st.caption(f"📅 {video.upload_date}")
    with col3:
        if video.duration_seconds:
            duration_min = video.duration_seconds // 60
            duration_sec = video.duration_seconds % 60
            st.caption(f"⏱️ {duration_min}:{duration_sec:02d}")
    with col4:
        st.caption(f"📝 {video.transcript_source}")

    # Tags (if available)
    if video.tags:
        try:
            tags_list = json.loads(video.tags)
            if tags_list:
                st.caption("🏷️ " + " • ".join([f"`{tag}`" for tag in tags_list[:10]]))  # Show first 10 tags
        except:
            pass

    # Video description (collapsible)
    if video.description:
        with st.expander("📄 Video Description", expanded=False):
            st.markdown(video.description)

    # Full transcript viewer (collapsible)
    with st.expander("📜 View Full Transcript", expanded=False):
        try:
            transcript_data = json.loads(video.raw_transcript)
            st.caption(f"Total segments: {len(transcript_data)}")

            # Display transcript with timestamps
            transcript_text = ""
            for entry in transcript_data:
                timestamp = format_timestamp(entry["start"])
                transcript_text += f"**[{timestamp}]** {entry['text']}\n\n"

            st.markdown(transcript_text)

            # Download button
            st.download_button(
                label="💾 Download Transcript (TXT)",
                data=transcript_text,
                file_name=f"{video.video_id}_transcript.txt",
                mime="text/plain"
            )
        except Exception as e:
            st.error(f"Failed to load transcript: {str(e)}")

    # Get segments (needed for export)
    with get_session() as session:
        segments = session.query(Segment).filter_by(video_id=video.id).order_by(Segment.start_seconds).all()

    # Export section
    st.markdown("---")
    st.markdown("### 💾 Export Summary")

    col1, col2, col3 = st.columns(3)

    with col1:
        # Export English Markdown
        try:
            markdown_en = export_video_to_markdown(video, segments, language="en")
            st.download_button(
                label="📥 Download English (MD)",
                data=markdown_en,
                file_name=f"{video.video_id}_summary_en.md",
                mime="text/markdown",
                help="Export summary with English content"
            )
        except Exception as e:
            st.error(f"Export failed: {str(e)}")

    with col2:
        # Export Chinese Markdown
        try:
            markdown_zh = export_video_to_markdown(video, segments, language="zh")
            st.download_button(
                label="📥 Download Chinese (MD)",
                data=markdown_zh,
                file_name=f"{video.video_id}_summary_zh.md",
                mime="text/markdown",
                help="Export summary with Chinese content"
            )
        except Exception as e:
            st.error(f"Export failed: {str(e)}")

    with col3:
        st.caption("💡 Markdown files can be opened in Notion, Obsidian, or any text editor")

    st.markdown("---")

    # Language tabs
    tab_en, tab_zh = st.tabs(["🇬🇧 English", "🇨🇳 中文"])

    # English tab
    with tab_en:
        st.markdown("### 📋 TL;DR")
        st.info(video.tldr)

        st.markdown("---")
        st.markdown("### 🕒 Timeline")

        for segment in segments:
            youtube_link = f"{video.source_url}&t={int(segment.start_seconds)}s"
            end_timestamp = f"{int(segment.end_seconds // 60):02d}:{int(segment.end_seconds % 60):02d}"

            with st.container():
                col1, col2 = st.columns([1, 5])
                with col1:
                    st.markdown(f"**[{segment.timestamp}]({youtube_link})**")
                    st.caption(f"to {end_timestamp}")
                with col2:
                    st.markdown(segment.summary)
                st.markdown("")

    # Chinese tab
    with tab_zh:
        st.markdown("### 📋 概要")
        st.info(video.tldr_zh)

        st.markdown("---")
        st.markdown("### 🕒 时间线")

        for segment in segments:
            youtube_link = f"{video.source_url}&t={int(segment.start_seconds)}s"
            end_timestamp = f"{int(segment.end_seconds // 60):02d}:{int(segment.end_seconds % 60):02d}"

            with st.container():
                col1, col2 = st.columns([1, 5])
                with col1:
                    st.markdown(f"**[{segment.timestamp}]({youtube_link})**")
                    st.caption(f"至 {end_timestamp}")
                with col2:
                    st.markdown(segment.summary_zh)
                st.markdown("")


def view_new_video():
    """Render the New Video view."""
    st.title("➕ Process New Video")

    # Input
    url = st.text_input(
        "YouTube URL",
        placeholder="https://www.youtube.com/watch?v=...",
        help="Enter a YouTube video URL to generate summary"
    )

    # Configuration options
    st.markdown("---")
    st.markdown("### ⚙️ Processing Options")

    col1, col2, col3 = st.columns(3)

    with col1:
        transcript_source = st.radio(
            "Transcript Source",
            ["Auto (Prefer YouTube)", "Force Whisper ASR"],
            help="Auto: Try YouTube captions first, fallback to ASR. Force: Always use Whisper ASR."
        )
        force_asr = (transcript_source == "Force Whisper ASR")

    with col2:
        # Build whisper model options with details
        whisper_options = []
        whisper_display = {}
        for key, info in WHISPER_MODELS.items():
            display_name = f"{key.capitalize()} - {info['size']}"
            whisper_options.append(display_name)
            whisper_display[display_name] = key

        whisper_choice = st.selectbox(
            "Whisper Model",
            whisper_options,
            index=3,  # Default to "medium" (4th item)
            help="Model size affects speed vs accuracy. Only used if ASR is needed."
        )
        whisper_model = whisper_display[whisper_choice]

        # Show model details
        model_info = WHISPER_MODELS[whisper_model]
        st.caption(f"{model_info['speed']} | {model_info['accuracy']}")

    with col3:
        # Build claude model options with details
        claude_options = []
        claude_display = {}
        for key, info in CLAUDE_MODELS.items():
            display_name = f"{key.capitalize()} - {info['name']}"
            claude_options.append(display_name)
            claude_display[display_name] = key

        claude_choice = st.selectbox(
            "Claude Model",
            claude_options,
            index=1,  # Default to "sonnet" (2nd item)
            help="Model affects quality and cost. Sonnet recommended for most use cases."
        )
        claude_model = claude_display[claude_choice]

        # Show model details
        model_info = CLAUDE_MODELS[claude_model]
        st.caption(f"{model_info['quality']} | {model_info['cost']}")

    st.markdown("---")

    if st.button("Process Video", type="primary", disabled=not url):
        if not validate_youtube_url(url):
            st.error("❌ Invalid YouTube URL. Please check and try again.")
            return

        try:
            # Check if already processed
            video_id = extract_video_id(url)
            with get_session() as session:
                existing = session.query(Video).filter_by(video_id=video_id).first()

            if existing:
                st.success("✅ Video already processed! Showing cached result:")
                render_video_result(existing)
            else:
                # Process new video with progress tracking
                status_container = st.status("🔄 Processing video...", expanded=True)
                steps = []

                def update_status(step: str, state: str):
                    """Callback to update UI status."""
                    if state == "running":
                        steps.append({"step": step, "state": "running"})
                        with status_container:
                            st.write(f"⏳ {step}...")
                    elif state == "success":
                        # Update the last running step or add new success
                        with status_container:
                            st.write(f"✅ {step}")
                    elif state == "error":
                        with status_container:
                            st.write(f"❌ {step}")

                # Process video with status callback and user configuration
                video = process_youtube_video(
                    url,
                    status_callback=update_status,
                    force_asr=force_asr,
                    whisper_model=whisper_model,
                    claude_model=claude_model
                )

                status_container.update(label="✅ Video processed successfully!", state="complete", expanded=False)
                render_video_result(video)

        except Exception as e:
            st.error(f"❌ Error processing video: {str(e)}")
            st.exception(e)


def view_history():
    """Render the History view with all videos and collections."""
    st.title("📜 History")

    # Handle delete collection confirmation (at top for visibility)
    if st.session_state.get("confirm_delete_collection_id"):
        collection_id = st.session_state.confirm_delete_collection_id

        st.error("⚠️ **DELETE COLLECTION CONFIRMATION**")
        st.warning("Are you sure you want to delete this collection AND all its videos? This cannot be undone.")

        col1, col2, col3 = st.columns([1, 1, 3])

        with col1:
            if st.button("❌ Cancel", key="cancel_delete_collection", use_container_width=True):
                del st.session_state.confirm_delete_collection_id
                st.rerun()

        with col2:
            if st.button("🗑️ Delete Collection", type="primary", key="confirm_delete_collection", use_container_width=True):
                try:
                    if delete_collection(collection_id):
                        st.success("✅ Collection deleted successfully")
                        del st.session_state.confirm_delete_collection_id
                        st.rerun()
                    else:
                        st.error("❌ Failed to delete collection - not found")
                except Exception as e:
                    st.error(f"❌ Error deleting collection: {str(e)}")
                    st.exception(e)

        st.markdown("---")

    # Get all videos and collections
    videos = get_all_videos()
    collections = get_all_collections()

    if not videos and not collections:
        st.info("No videos processed yet. Process your first video from the sidebar!")
        return

    # Display collections
    if collections:
        st.markdown("### 📚 Collections")
        for collection in collections:
            with st.expander(f"📚 {collection.title} ({len(collection.videos)} videos)", expanded=False):
                if collection.description:
                    st.info(collection.description)

                if collection.videos:
                    # Display videos in order
                    sorted_videos = sorted(collection.videos, key=lambda v: v.order_index or 0)
                    for idx, video in enumerate(sorted_videos):
                        st.markdown(f"**{idx + 1}. {video.title}**")
                        st.caption(video.tldr[:150] + "..." if len(video.tldr) > 150 else video.tldr)

                        col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])
                        with col1:
                            if st.button("📄 View", key=f"view_col_{video.id}"):
                                st.session_state.selected_video_id = video.id
                                st.rerun()
                        with col2:
                            # Move up button (disabled if first)
                            if st.button("⬆️ Up", key=f"up_{video.id}", disabled=(idx == 0)):
                                if move_video_in_collection(video.id, "up"):
                                    st.rerun()
                        with col3:
                            # Move down button (disabled if last)
                            if st.button("⬇️ Down", key=f"down_{video.id}", disabled=(idx == len(sorted_videos) - 1)):
                                if move_video_in_collection(video.id, "down"):
                                    st.rerun()
                        with col4:
                            if st.button("➖ Remove", key=f"remove_{video.id}"):
                                if remove_video_from_collection(video.id):
                                    st.success(f"✅ Removed from collection")
                                    st.rerun()
                        with col5:
                            if st.button("🗑️", key=f"del_col_{video.id}"):
                                st.session_state.confirm_delete_video_id = video.id
                                st.rerun()

                        st.markdown("")  # Spacing
                else:
                    st.info("No videos in this collection. Add videos from Standalone Videos below.")

                st.markdown("---")
                # Delete collection button
                col1, col2, col3 = st.columns([1, 1, 3])
                with col1:
                    if st.button(f"🗑️ Delete Collection", key=f"del_collection_{collection.id}"):
                        st.session_state.confirm_delete_collection_id = collection.id
                        st.rerun()

        st.markdown("---")

    # Display standalone videos
    if videos:
        st.markdown("### 🎬 Standalone Videos")

        for video in videos:
            with st.expander(f"🎬 {video.title}", expanded=False):
                st.caption(f"📺 {video.channel_name}")
                st.markdown(video.tldr[:200] + "..." if len(video.tldr) > 200 else video.tldr)

                st.markdown("")  # Spacing

                # Action buttons
                col1, col2, col3 = st.columns([2, 2, 1])
                with col1:
                    if st.button(f"📄 View Full Summary", key=f"view_standalone_{video.id}", use_container_width=True):
                        st.session_state.selected_video_id = video.id
                        st.rerun()
                with col2:
                    # Add to collection dropdown with button
                    if collections:
                        collection_options = {col.title: col.id for col in collections}
                        selected_collection = st.selectbox(
                            "➕ Add to Collection:",
                            options=["Choose a collection..."] + list(collection_options.keys()),
                            key=f"addto_{video.id}",
                            help="Select a collection to add this video to"
                        )
                        if selected_collection != "Choose a collection...":
                            if add_video_to_collection(video.id, collection_options[selected_collection]):
                                st.success(f"✅ Added to '{selected_collection}'")
                                st.rerun()
                    else:
                        st.info("💡 Create a collection first")
                with col3:
                    if st.button(f"🗑️ Delete", key=f"del_standalone_{video.id}", use_container_width=True):
                        st.session_state.confirm_delete_video_id = video.id
                        st.rerun()

    # Handle view selected video
    if st.session_state.get("selected_video_id"):
        video_id = st.session_state.selected_video_id
        with get_session() as session:
            video = session.query(Video).filter_by(id=video_id).first()

        if video:
            st.markdown("---")
            render_video_result(video)

            if st.button("← Back to History"):
                del st.session_state.selected_video_id
                st.rerun()

    # Handle delete confirmation
    if st.session_state.get("confirm_delete_video_id"):
        video_id = st.session_state.confirm_delete_video_id

        st.warning("⚠️ Are you sure you want to delete this video? This cannot be undone.")
        col1, col2, col3 = st.columns([1, 1, 3])

        with col1:
            if st.button("Cancel", key="cancel_delete"):
                del st.session_state.confirm_delete_video_id
                st.rerun()

        with col2:
            if st.button("Delete", type="primary", key="confirm_delete"):
                if delete_video(video_id):
                    st.success("✅ Video deleted")
                    del st.session_state.confirm_delete_video_id
                    st.rerun()
                else:
                    st.error("❌ Failed to delete video")


def view_new_collection():
    """Render the New Collection view."""
    st.title("📚 Create New Collection")
    st.caption("Create an empty collection, then add existing videos from History")

    # Create collection form
    with st.form("create_collection_form"):
        title = st.text_input(
            "Collection Title *",
            placeholder="e.g., Python Programming Course",
            help="Required: Give your collection a descriptive name"
        )

        description = st.text_area(
            "Description (Optional)",
            placeholder="e.g., A comprehensive course covering Python fundamentals...",
            help="Optional: Add more details about this collection"
        )

        submitted = st.form_submit_button("Create Collection", type="primary")

        if submitted:
            if not title or not title.strip():
                st.error("❌ Title is required")
            else:
                try:
                    collection = create_collection(title.strip(), description.strip() if description else None)
                    st.success(f"✅ Collection '{collection.title}' created successfully!")
                    st.info("💡 Go to History to add videos to this collection")
                except Exception as e:
                    st.error(f"❌ Error creating collection: {str(e)}")

    st.markdown("---")

    # Show existing collections
    collections = get_all_collections()
    if collections:
        st.markdown("### 📚 Existing Collections")
        for col in collections:
            with st.expander(f"📚 {col.title} ({len(col.videos)} videos)"):
                if col.description:
                    st.markdown(f"**Description:** {col.description}")
                st.caption(f"Created: {col.created_at.strftime('%Y-%m-%d %H:%M')}")

                if col.videos:
                    st.markdown("**Videos:**")
                    for video in sorted(col.videos, key=lambda v: v.order_index or 0):
                        st.markdown(f"{video.order_index + 1}. {video.title}")
                else:
                    st.info("No videos in this collection yet")


def main():
    """Main app entry point."""

    # Initialize database (creates tables if they don't exist)
    # This is idempotent - safe to call every time
    init_db()

    # Check password
    if not check_password():
        return

    # Sidebar navigation
    st.sidebar.title("🎬 tldr-tube")
    st.sidebar.markdown("---")

    view = st.sidebar.radio(
        "Navigation",
        ["➕ New Video", "📜 History", "📚 New Collection"],
        label_visibility="collapsed"
    )

    st.sidebar.markdown("---")
    st.sidebar.caption("YouTube video summarizer with timestamp-anchored summaries")

    # Route to view
    if view == "➕ New Video":
        view_new_video()
    elif view == "📜 History":
        view_history()
    elif view == "📚 New Collection":
        view_new_collection()


if __name__ == "__main__":
    main()
