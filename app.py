"""
tldr-tube - Streamlit Web App

YouTube video summarizer with timestamp-anchored summaries.
"""

import os
import streamlit as st
from dotenv import load_dotenv

from db.session import init_db, get_session
from db.models import Video, Segment, Collection
from pipeline.processor import process_youtube_video, get_all_videos, delete_video
from pipeline.utils import validate_youtube_url, extract_video_id

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

    col1, col2, col3 = st.columns(3)
    with col1:
        st.caption(f"📺 {video.channel_name}")
    with col2:
        if video.duration_seconds:
            duration_min = video.duration_seconds // 60
            duration_sec = video.duration_seconds % 60
            st.caption(f"⏱️ {duration_min}:{duration_sec:02d}")
    with col3:
        st.caption(f"📝 Transcript: {video.transcript_source}")

    # TL;DR
    st.markdown("---")
    st.markdown("### 📋 TL;DR")
    st.info(video.tldr)

    # Segments
    st.markdown("---")
    st.markdown("### 🕒 Timeline")

    # Get segments
    with get_session() as session:
        segments = session.query(Segment).filter_by(video_id=video.id).order_by(Segment.start_seconds).all()

    for segment in segments:
        # Create clickable YouTube timestamp link
        youtube_link = f"{video.source_url}&t={int(segment.start_seconds)}s"

        # Format time range
        end_timestamp = f"{int(segment.end_seconds // 60):02d}:{int(segment.end_seconds % 60):02d}"
        time_range = f"{segment.timestamp} - {end_timestamp}"

        # Display segment
        with st.container():
            col1, col2 = st.columns([1, 5])
            with col1:
                st.markdown(f"**[{segment.timestamp}]({youtube_link})**")
                st.caption(f"to {end_timestamp}")
            with col2:
                st.markdown(segment.summary)

            st.markdown("")  # Spacing


def view_new_video():
    """Render the New Video view."""
    st.title("➕ Process New Video")

    # Input
    url = st.text_input(
        "YouTube URL",
        placeholder="https://www.youtube.com/watch?v=...",
        help="Enter a YouTube video URL to generate summary"
    )

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

                # Process video with status callback
                video = process_youtube_video(url, status_callback=update_status)

                status_container.update(label="✅ Video processed successfully!", state="complete", expanded=False)
                render_video_result(video)

        except Exception as e:
            st.error(f"❌ Error processing video: {str(e)}")
            st.exception(e)


def view_history():
    """Render the History view with all videos and collections."""
    st.title("📜 History")

    # Get all videos
    videos = get_all_videos()

    # Get all collections
    with get_session() as session:
        collections = session.query(Collection).order_by(Collection.created_at.desc()).all()

    if not videos and not collections:
        st.info("No videos processed yet. Process your first video from the sidebar!")
        return

    # Display collections
    if collections:
        st.markdown("### 📚 Collections")
        for collection in collections:
            with st.expander(f"📚 {collection.title} ({len(collection.videos)} videos)"):
                if collection.description:
                    st.caption(collection.description)

                for video in sorted(collection.videos, key=lambda v: v.order_index or 0):
                    st.markdown(f"**{video.title}**")
                    st.caption(video.tldr[:200] + "..." if len(video.tldr) > 200 else video.tldr)

                    col1, col2 = st.columns([3, 1])
                    with col1:
                        if st.button(f"View Full Summary", key=f"view_{video.id}"):
                            st.session_state.selected_video_id = video.id
                    with col2:
                        if st.button(f"🗑️ Delete", key=f"del_{video.id}"):
                            st.session_state.confirm_delete_video_id = video.id

                    st.markdown("---")

                # Delete collection button
                if st.button(f"🗑️ Delete Collection", key=f"del_collection_{collection.id}"):
                    st.session_state.confirm_delete_collection_id = collection.id

        st.markdown("---")

    # Display standalone videos
    if videos:
        st.markdown("### 🎬 Standalone Videos")

        for video in videos:
            with st.expander(f"🎬 {video.title}"):
                st.caption(f"📺 {video.channel_name}")
                st.markdown(video.tldr)

                col1, col2 = st.columns([3, 1])
                with col1:
                    if st.button(f"View Full Summary", key=f"view_standalone_{video.id}"):
                        st.session_state.selected_video_id = video.id
                with col2:
                    if st.button(f"🗑️ Delete", key=f"del_standalone_{video.id}"):
                        st.session_state.confirm_delete_video_id = video.id

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
    st.caption("Process multiple videos and group them as a collection (e.g., a course)")

    # TODO: Implement collection creation
    st.info("🚧 Collection creation coming soon!")

    st.markdown("""
    **Planned features:**
    - Enter collection title and description
    - Paste multiple YouTube URLs (one per line)
    - Process all videos sequentially
    - View collection summary with all videos in order
    """)


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
