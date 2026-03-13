"""
tldr-tube - Streamlit Web App

YouTube and Bilibili video summarizer with timestamp-anchored summaries.
"""

import os
import json
import streamlit as st
from dotenv import load_dotenv

from db.session import init_db, get_session
from db.models import Video, Segment, Collection, Keyframe, Note, ProcessingJob
from db.operations import (
    create_collection, add_video_to_collection, remove_video_from_collection,
    move_video_in_collection, delete_collection, get_all_collections,
    create_job, create_notes_job, get_all_jobs, delete_job, clear_finished_jobs,
)
from pipeline.processor import process_video, get_all_videos, delete_video
from pipeline.worker import start_queue_worker, get_job_progress
from pipeline.utils import (
    validate_video_url, validate_youtube_url, extract_video_id, extract_bilibili_id,
    extract_deeplearning_id, extract_deeplearning_course_slug,
    detect_source_type, generate_timestamp_link, format_timestamp
)
from pipeline.metadata import fetch_deeplearning_course_lessons
from pipeline.config import WHISPER_MODELS, CLAUDE_MODELS, LLM_PROVIDERS, check_api_key_configured, get_available_providers
from pipeline.export import export_video_to_markdown, export_collection_to_markdown
from pipeline.search import hybrid_search
from pipeline.rag import answer_question

# Load environment variables
load_dotenv()

# Page config
st.set_page_config(
    page_title="tldr-tube",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

_PLATFORM_ICONS = {"bilibili": "🅱️", "deeplearning_ai": "🎓"}
_PLATFORM_NAMES = {"bilibili": "Bilibili", "deeplearning_ai": "DeepLearning.AI"}


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

    st.caption("Set APP_PASSWORD in .env to enable password protection, or leave it unset to skip this screen.")

    return False


def _render_notes_section(video: Video):
    """Render the notes display section if notes exist."""
    with get_session() as session:
        notes = session.query(Note).filter_by(video_id=video.id).order_by(Note.order_index).all()
        if not notes:
            return

        # Load all keyframes for this video into a lookup
        all_kfs = {kf.id: kf for kf in session.query(Keyframe).filter_by(video_id=video.id).all()}

        st.markdown("---")
        st.markdown("### 📝 Study Notes")
        st.caption(f"{len(notes)} topics | {sum(len(json.loads(n.keyframe_ids)) for n in notes)} keyframes referenced")

        tab_en, tab_zh = st.tabs(["🇬🇧 English", "🇨🇳 中文"])

        for tab, lang in [(tab_en, "en"), (tab_zh, "zh")]:
            with tab:
                for note in notes:
                    title = note.title if lang == "en" else (note.title_zh or note.title)
                    content = note.notes if lang == "en" else (note.notes_zh or note.notes)

                    kf_ids = json.loads(note.keyframe_ids)
                    kf_objects = [all_kfs[kid] for kid in kf_ids if kid in all_kfs]

                    with st.expander(f"**{title}**", expanded=True):
                        # Keyframe gallery (small thumbnails, click to enlarge)
                        if kf_objects:
                            for kf in kf_objects:
                                if os.path.exists(kf.frame_path):
                                    st.image(kf.frame_path, caption=kf.timestamp_str, width=640)

                        st.markdown(content)


def render_video_result(video: Video):
    """
    Render a processed video's summary and segments.

    Args:
        video: Video object from database
    """
    # Header with metadata
    icon = _PLATFORM_ICONS.get(video.source_type, "▶️")
    platform = _PLATFORM_NAMES.get(video.source_type, "YouTube")
    st.markdown(f"## {icon} {video.title}")

    # Basic metadata row
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.caption(f"📺 {video.channel_name}")
    with col2:
        if video.upload_date:
            st.caption(f"📅 {video.upload_date}")
    with col3:
        if video.duration_seconds:
            duration_min = int(video.duration_seconds) // 60
            duration_sec = int(video.duration_seconds) % 60
            st.caption(f"⏱️ {duration_min}:{duration_sec:02d}")
    with col4:
        st.caption(f"📝 {video.transcript_source}")
    with col5:
        st.markdown(f"[{icon} Watch on {platform}]({video.source_url})")

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

    # Generate Notes section
    if video.source_type in ("youtube", "deeplearning_ai"):
        st.markdown("---")
        st.markdown("### 📝 Generate Study Notes")

        # Check if notes already exist or a job is in progress
        with get_session() as session:
            has_notes = session.query(Note).filter_by(video_id=video.id).count() > 0
            pending_job = (
                session.query(ProcessingJob)
                .filter_by(target_video_id=video.id, job_type="generate_notes")
                .filter(ProcessingJob.status.in_(["pending", "processing"]))
                .first()
            )

        if pending_job:
            st.info("⏳ Note generation in progress — check the Queue tab for status.")
        else:
            note_col1, note_col2, note_col3 = st.columns([1, 1, 2])
            with note_col1:
                btn_label = "🔄 Regenerate Notes" if has_notes else "📝 Generate Notes"
                generate_clicked = st.button(btn_label, key=f"gen_notes_{video.id}")
            with note_col2:
                merge_batches = st.toggle("Merge sections", value=True, key=f"merge_{video.id}",
                                          help="Merge small adjacent sections into larger batches for better context continuity and fewer LLM calls. Disable to generate notes per section independently.")
            with note_col3:
                if has_notes:
                    st.caption("✅ Notes available — scroll down to view")
                else:
                    st.caption("Extract keyframes from the video and generate concept-based bilingual study notes using a multimodal LLM")

            if generate_clicked:
                if has_notes:
                    st.session_state[f"_confirm_regen_{video.id}"] = True
                    st.rerun()
                else:
                    create_notes_job(video.id, merge_batches=merge_batches)
                    st.session_state._nav_redirect = "📋 Queue"
                    st.rerun()

            # Regeneration confirmation
            if st.session_state.get(f"_confirm_regen_{video.id}"):
                st.warning("Existing notes will be replaced. Continue?")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Cancel", key=f"cancel_regen_{video.id}"):
                        del st.session_state[f"_confirm_regen_{video.id}"]
                        st.rerun()
                with c2:
                    if st.button("Regenerate", type="primary", key=f"confirm_regen_{video.id}"):
                        del st.session_state[f"_confirm_regen_{video.id}"]
                        create_notes_job(video.id, merge_batches=merge_batches)
                        st.session_state._nav_redirect = "📋 Queue"
                        st.rerun()

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
            youtube_link = generate_timestamp_link(video.source_url, video.source_type, int(segment.start_seconds))
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
            youtube_link = generate_timestamp_link(video.source_url, video.source_type, int(segment.start_seconds))
            end_timestamp = f"{int(segment.end_seconds // 60):02d}:{int(segment.end_seconds % 60):02d}"

            with st.container():
                col1, col2 = st.columns([1, 5])
                with col1:
                    st.markdown(f"**[{segment.timestamp}]({youtube_link})**")
                    st.caption(f"至 {end_timestamp}")
                with col2:
                    st.markdown(segment.summary_zh)
                st.markdown("")

    # Notes display (after timeline)
    _render_notes_section(video)


def view_new_video():
    """Render the New Video view."""
    st.title("➕ Process New Video")

    # ── DeepLearning.AI course confirmation ───────────────────────────────────
    if st.session_state.get("_dl_course_pending"):
        info = st.session_state["_dl_course_pending"]
        locked = info.get("locked_count", 0)
        lock_note = f" ({locked} locked — login required)" if locked else ""
        st.info(
            f"🎓 Detected DeepLearning.AI course: **{info['course_name']}**  \n"
            f"Found **{len(info['lessons'])}** accessible video lesson(s){lock_note}. Process all as a Collection?"
        )
        with st.expander("View lessons"):
            for i, lesson in enumerate(info["lessons"]):
                st.caption(f"{i + 1}. {lesson['title']}")

        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("✅ Create Collection", type="primary"):
                try:
                    collection = create_collection(info["course_name"])
                    for lesson in info["lessons"]:
                        create_job(
                            url=lesson["url"],
                            force_asr=info["force_asr"],
                            whisper_model=info["whisper_model"],
                            provider=info["provider"],
                            model=info["model"],
                            collection_id=collection.id,
                            order_index=lesson["order_index"],
                        )
                    del st.session_state["_dl_course_pending"]
                    st.session_state._nav_redirect = "📋 Queue"
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Failed to create collection: {str(e)}")
        with col2:
            if st.button("❌ Cancel"):
                del st.session_state["_dl_course_pending"]
                st.rerun()
        return
    # ─────────────────────────────────────────────────────────────────────────

    # Input
    url = st.text_input(
        "Video URL",
        placeholder="https://www.youtube.com/watch?v=... or https://learn.deeplearning.ai/...",
        help="Enter a YouTube, Bilibili, or DeepLearning.AI URL. Paste a course URL to process all lessons as a Collection."
    )

    # Configuration options
    st.markdown("---")
    st.markdown("### ⚙️ Processing Options")

    col1, col2, col3 = st.columns(3)

    with col1:
        transcript_source = st.radio(
            "Transcript Source",
            ["Auto (Prefer captions)", "Force Whisper ASR"],
            help="Auto: Try platform captions first, fallback to ASR. Force: Always use Whisper ASR."
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
        # Check available providers
        available_providers = get_available_providers()

        # LLM Provider selection
        provider_names = {
            "claude": "Claude (Recommended ⭐)",
            "deepseek": "DeepSeek 💎 (95% Cheaper!)",
            "gemini": "Gemini",
            "openai": "OpenAI",
            "qwen": "Qwen 🇨🇳 (Best Chinese)"
        }

        def format_provider_name(provider):
            name = provider_names.get(provider, LLM_PROVIDERS[provider]["name"])
            if not available_providers[provider]["available"]:
                name += " ⚠️"
            return name

        selected_provider = st.selectbox(
            "LLM Provider",
            options=list(LLM_PROVIDERS.keys()),
            format_func=format_provider_name,
            index=0,  # Default to Claude Sonnet
            help="Claude Sonnet: Best quality. DeepSeek: Best value (95% cheaper)."
        )

        # Show warning if selected provider is not configured
        if not available_providers[selected_provider]["available"]:
            hint = (available_providers[selected_provider].get("setup_hint")
                    or f"Set {available_providers[selected_provider]['api_key_env']} in your .env file")
            st.warning(f"⚠️ {hint}")

    # Model selection in a new row
    col1, col2, col3 = st.columns(3)
    with col1:
        st.empty()  # Spacer
    with col2:
        st.empty()  # Spacer
    with col3:
        # Get available models for selected provider
        available_models = LLM_PROVIDERS[selected_provider]["models"]

        # Build model options
        model_options = []
        model_display = {}
        for key, info in available_models.items():
            display_name = f"{key.capitalize()} - {info['name']}"
            model_options.append(display_name)
            model_display[display_name] = key

        # Default model index
        default_model = LLM_PROVIDERS[selected_provider]["default_model"]
        default_index = list(available_models.keys()).index(default_model)

        model_choice = st.selectbox(
            f"{LLM_PROVIDERS[selected_provider]['name']} Model",
            model_options,
            index=default_index,
            help="Model affects quality and cost"
        )
        selected_model = model_display[model_choice]

        # Show model details
        model_info = available_models[selected_model]
        st.caption(f"{model_info.get('quality', '')} | {model_info['cost']}")

    st.markdown("---")

    # Check if selected provider is available before allowing processing
    provider_available = check_api_key_configured(selected_provider)

    if st.button("Add to Queue", type="primary", disabled=not url or not provider_available):
        if "deeplearning.ai" in url and "learn.deeplearning.ai" not in url:
            st.error("❌ Please use the learn.deeplearning.ai URL, e.g. https://learn.deeplearning.ai/courses/...")
            return

        if not validate_video_url(url):
            st.error("❌ Invalid URL. Supported platforms: YouTube, Bilibili, and DeepLearning.AI.")
            return

        source_type = detect_source_type(url)

        # Course URL → fetch lesson list and ask for confirmation
        if source_type == "deeplearning_course":
            with st.spinner("Fetching course info..."):
                try:
                    course_name, lessons, locked_count = fetch_deeplearning_course_lessons(url)
                    st.session_state["_dl_course_pending"] = {
                        "course_name": course_name,
                        "lessons": lessons,
                        "locked_count": locked_count,
                        "force_asr": force_asr,
                        "whisper_model": whisper_model,
                        "provider": selected_provider,
                        "model": selected_model,
                    }
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Failed to fetch course info: {str(e)}")
            return

        # Single video URL → check cache then enqueue
        if source_type == "youtube":
            video_id = extract_video_id(url)
        elif source_type == "bilibili":
            video_id = extract_bilibili_id(url)
        else:
            video_id = extract_deeplearning_id(url)

        with get_session() as session:
            existing = session.query(Video).filter_by(video_id=video_id).first()

        if existing:
            st.success("✅ Video already processed! Showing cached result:")
            render_video_result(existing)
        else:
            create_job(
                url=url,
                force_asr=force_asr,
                whisper_model=whisper_model,
                provider=selected_provider,
                model=selected_model,
            )
            st.session_state._nav_redirect = "📋 Queue"
            st.rerun()


def view_history():
    """Render the History view with all videos and collections."""
    # Dynamic title based on current view state
    if st.session_state.get("selected_video_id"):
        st.title("🎬 Video Detail")
    elif st.session_state.get("selected_collection_id"):
        st.title("📂 Collection")
    else:
        st.title("📚 Library")

    # Handle delete video confirmation (at top for visibility)
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
                    del st.session_state.confirm_delete_video_id
                    st.toast("✅ Video deleted")
                    st.rerun()
                else:
                    st.error("❌ Failed to delete video")

        st.markdown("---")
        return

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
    all_videos = get_all_videos()
    collections = get_all_collections()

    if not all_videos and not collections:
        st.info("No videos processed yet. Process your first video from the sidebar!")
        return

    # Show selected video detail (replaces library list)
    if st.session_state.get("selected_video_id"):
        video_id = st.session_state.selected_video_id
        # Determine back target: collection or library
        back_collection_id = st.session_state.get("_back_to_collection")
        back_label = "← Back to Collection" if back_collection_id else "← Back to Library"

        def _back_from_video():
            del st.session_state.selected_video_id
            if not back_collection_id and "_back_to_collection" in st.session_state:
                del st.session_state._back_to_collection

        with get_session() as session:
            video = session.query(Video).filter_by(id=video_id).first()

        if video:
            if st.button(back_label):
                _back_from_video()
                st.rerun()
            render_video_result(video)
            if st.button(back_label, key="back_bottom"):
                _back_from_video()
                st.rerun()
            return

    # Show selected collection detail (replaces library list)
    if st.session_state.get("selected_collection_id"):
        col_id = st.session_state.selected_collection_id
        with get_session() as session:
            from sqlalchemy.orm import joinedload
            collection = (
                session.query(Collection)
                .options(joinedload(Collection.videos))
                .filter_by(id=col_id)
                .first()
            )
            if collection:
                videos_in_col = sorted(collection.videos, key=lambda v: v.order_index or 0)
                session.expunge_all()

        if collection:
            if st.button("← Back to Library"):
                del st.session_state.selected_collection_id
                st.rerun()

            st.markdown(f"### 📂 {collection.title} ({len(videos_in_col)} videos)")
            if collection.description:
                st.info(collection.description)

            if videos_in_col:
                # Note generation status
                with get_session() as session:
                    videos_with_notes = {
                        v.id for v in videos_in_col
                        if session.query(Note).filter_by(video_id=v.id).count() > 0
                    }
                    videos_with_pending = {
                        v.id for v in videos_in_col
                        if session.query(ProcessingJob)
                        .filter_by(target_video_id=v.id, job_type="generate_notes")
                        .filter(ProcessingJob.status.in_(["pending", "processing"]))
                        .first()
                    }

                eligible = [v for v in videos_in_col
                            if v.source_type in ("youtube", "deeplearning_ai")
                            and v.id not in videos_with_pending]
                without_notes = [v for v in eligible if v.id not in videos_with_notes]
                with_notes = [v for v in eligible if v.id in videos_with_notes]

                # Action toolbar
                action_buttons = []
                if eligible and without_notes:
                    action_buttons.append(("gen", f"📝 Generate Notes ({len(without_notes)})"))
                if eligible and with_notes:
                    action_buttons.append(("regen", f"🔄 Regenerate All Notes ({len(eligible)})"))
                action_buttons.append(("delete", "🗑️ Delete Collection"))

                cols = st.columns(len(action_buttons))
                for col, (action, label) in zip(cols, action_buttons):
                    with col:
                        if st.button(label, key=f"{action}_{collection.id}", use_container_width=True):
                            if action == "gen":
                                for v in without_notes:
                                    create_notes_job(v.id)
                                st.session_state._nav_redirect = "📋 Queue"
                                st.rerun()
                            elif action == "regen":
                                st.session_state[f"_confirm_regen_col_{collection.id}"] = True
                                st.rerun()
                            elif action == "delete":
                                st.session_state.confirm_delete_collection_id = collection.id
                                del st.session_state.selected_collection_id
                                st.rerun()

                if st.session_state.get(f"_confirm_regen_col_{collection.id}"):
                    st.warning(f"This will regenerate notes for all {len(eligible)} videos. Existing notes will be replaced.")
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("Cancel", key=f"cancel_regen_col_{collection.id}"):
                            del st.session_state[f"_confirm_regen_col_{collection.id}"]
                            st.rerun()
                    with c2:
                        if st.button("Regenerate All", type="primary", key=f"confirm_regen_col_{collection.id}"):
                            del st.session_state[f"_confirm_regen_col_{collection.id}"]
                            for v in eligible:
                                create_notes_job(v.id)
                            st.session_state._nav_redirect = "📋 Queue"
                            st.rerun()

                st.markdown("---")

                # Video list
                for idx, video in enumerate(videos_in_col):
                    note_badge = " ✅" if video.id in videos_with_notes else ""
                    st.markdown(f"**{idx + 1}. {video.title}**{note_badge}")
                    st.caption(video.tldr[:150] + "..." if len(video.tldr) > 150 else video.tldr)

                    col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])
                    with col1:
                        if st.button("📄 View", key=f"view_col_{video.id}"):
                            st.session_state.selected_video_id = video.id
                            st.session_state._back_to_collection = collection.id
                            st.rerun()
                    with col2:
                        if st.button("⬆️ Up", key=f"up_{video.id}", disabled=(idx == 0)):
                            if move_video_in_collection(video.id, "up"):
                                st.rerun()
                    with col3:
                        if st.button("⬇️ Down", key=f"down_{video.id}", disabled=(idx == len(videos_in_col) - 1)):
                            if move_video_in_collection(video.id, "down"):
                                st.rerun()
                    with col4:
                        if st.button("➖ Remove", key=f"remove_{video.id}"):
                            if remove_video_from_collection(video.id):
                                st.toast("Removed from collection")
                                st.rerun()
                    with col5:
                        if st.button("🗑️", key=f"del_col_{video.id}"):
                            st.session_state.confirm_delete_video_id = video.id
                            st.rerun()

                    st.markdown("")
            else:
                st.info("No videos in this collection.")
                if st.button("🗑️ Delete Collection", key=f"del_collection_{collection.id}"):
                    st.session_state.confirm_delete_collection_id = collection.id
                    del st.session_state.selected_collection_id
                    st.rerun()

            if st.button("← Back to Library", key="back_col_bottom"):
                del st.session_state.selected_collection_id
                st.rerun()
            return

    # Search functionality
    st.markdown("### 🔍 Search")
    search_query = st.text_input(
        "Search videos by title, content, or tags",
        placeholder="e.g., Python decorators, async programming, 装饰器...",
        help="Search in video titles, TL;DR summaries, segments, descriptions, and tags",
        key="search_query"
    )

    # Filter videos based on search query (hybrid: semantic + keyword)
    if search_query and search_query.strip():
        query = search_query.strip()

        # Use hybrid search (combines semantic similarity + keyword matching)
        search_results = hybrid_search(
            query,
            top_k=20,
            semantic_weight=0.7,
            keyword_weight=0.3,
            min_semantic_score=0.3
        )

        if search_results:
            # Extract videos and display match info
            videos = [video for video, score, match_info in search_results]

            # Show search results summary
            st.success(f"✅ Found {len(videos)} video(s) matching '{search_query}'")

            # Show match type breakdown
            match_types = {}
            for _, score, match_info in search_results:
                match_types[match_info] = match_types.get(match_info, 0) + 1

            match_summary = " | ".join([f"{k}: {v}" for k, v in match_types.items()])
            st.caption(f"Search results: {match_summary}")
        else:
            st.warning(f"⚠️ No videos found matching '{search_query}'")
            st.info("💡 Try different keywords or check spelling")
            return
    else:
        videos = all_videos

    st.markdown("---")

    # Display collections
    if collections:
        st.markdown("### 📂 Collections")
        for collection in collections:
            with st.expander(f"📂 {collection.title} ({len(collection.videos)} videos)", expanded=False):
                if collection.description:
                    st.caption(collection.description)

                # Show first few video titles as preview
                if collection.videos:
                    sorted_vids = sorted(collection.videos, key=lambda v: v.order_index or 0)
                    preview = ", ".join(v.title for v in sorted_vids[:3])
                    if len(sorted_vids) > 3:
                        preview += f", ... (+{len(sorted_vids) - 3} more)"
                    st.markdown(preview)

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("📄 View Collection", key=f"open_col_{collection.id}", use_container_width=True):
                        st.session_state.selected_collection_id = collection.id
                        st.rerun()
                with col2:
                    if st.button("🗑️ Delete", key=f"del_col_list_{collection.id}", use_container_width=True):
                        st.session_state.confirm_delete_collection_id = collection.id
                        st.rerun()

        st.markdown("---")

    # Display standalone videos
    if videos:
        st.markdown("### 🎬 Standalone Videos")

        for video in videos:
            with st.expander(f"{_PLATFORM_ICONS.get(video.source_type, '▶️')} {video.title}", expanded=False):
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




def view_new_collection():
    """Render the New Collection view."""
    st.title("➕ Create New Collection")
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
        st.markdown("### 📂 Existing Collections")
        for col in collections:
            with st.expander(f"📂 {col.title} ({len(col.videos)} videos)"):
                if col.description:
                    st.markdown(f"**Description:** {col.description}")
                st.caption(f"Created: {col.created_at.strftime('%Y-%m-%d %H:%M')}")

                if col.videos:
                    st.markdown("**Videos:**")
                    for video in sorted(col.videos, key=lambda v: v.order_index or 0):
                        st.markdown(f"{video.order_index + 1}. {video.title}")
                else:
                    st.info("No videos in this collection yet")


def view_ask_ai():
    """Render the Ask AI view - RAG-based Q&A system."""
    st.title("🤖 Ask AI about Your Videos")
    st.caption("Ask questions and get AI-generated answers based on your processed videos")

    # Check if there are any videos
    all_videos = get_all_videos()
    with get_session() as session:
        collection_videos = session.query(Video).filter(Video.collection_id.isnot(None)).all()
        total_videos = len(all_videos) + len(collection_videos)

    if total_videos == 0:
        st.info("📺 No videos processed yet. Process some videos first to use this feature!")
        st.markdown("Go to **➕ New Video** to process your first video.")
        return

    st.info(f"📚 You have {total_videos} video(s) available for Q&A")

    # Provider, Model and Language selection
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        # Check available providers
        available_providers_rag = get_available_providers()

        # LLM Provider selection
        provider_names_rag = {
            "claude": "Claude (Recommended ⭐)",
            "deepseek": "DeepSeek 💎 (95% Cheaper!)",
            "gemini": "Gemini",
            "openai": "OpenAI",
            "qwen": "Qwen 🇨🇳 (Best Chinese)"
        }

        def format_provider_name_rag(provider):
            name = provider_names_rag.get(provider, LLM_PROVIDERS[provider]["name"])
            if not available_providers_rag[provider]["available"]:
                name += " ⚠️"
            return name

        selected_provider = st.selectbox(
            "LLM Provider",
            options=list(LLM_PROVIDERS.keys()),
            format_func=format_provider_name_rag,
            index=0,  # Default to Claude Sonnet
            key="rag_provider_select"
        )

        # Show warning if selected provider is not configured
        if not available_providers_rag[selected_provider]["available"]:
            api_key_env = available_providers_rag[selected_provider]["api_key_env"]
            st.warning(f"⚠️ {api_key_env} not configured. Add it to your .env file.")
    with col2:
        # Get available models for selected provider
        available_models = LLM_PROVIDERS[selected_provider]["models"]
        default_model = LLM_PROVIDERS[selected_provider]["default_model"]
        default_index = list(available_models.keys()).index(default_model)

        selected_model = st.selectbox(
            "Model",
            options=list(available_models.keys()),
            format_func=lambda x: available_models[x]["name"],
            index=default_index,
            key="rag_model_select"
        )
        model_info = available_models[selected_model]
        st.caption(f"{model_info['cost']}")
    with col3:
        answer_language = st.selectbox(
            "Answer Language",
            options=["Auto-detect", "English", "中文"],
            index=0,  # Default to Auto-detect
            key="rag_language_select"
        )
        # Map display names to language codes
        language_map = {
            "Auto-detect": None,
            "English": "en",
            "中文": "zh"
        }
        selected_language = language_map[answer_language]

    # Search Scope Selection
    with st.expander("🎯 Search Scope (Default: All Videos)", expanded=False):
        st.caption("Select which videos to search. More focused scope = higher accuracy")

        # Get all collections and videos
        collections = get_all_collections()

        # Initialize session state for selections if not exists
        if 'rag_selected_videos' not in st.session_state:
            # Default: select all videos
            all_video_ids = set()
            for video in all_videos:
                all_video_ids.add(video.id)
            with get_session() as session:
                for coll in collections:
                    for video in coll.videos:
                        all_video_ids.add(video.id)
            st.session_state.rag_selected_videos = all_video_ids

        # Compute full set of all video IDs
        all_ids = set(v.id for v in all_videos)
        for coll in collections:
            for v in coll.videos:
                all_ids.add(v.id)

        all_currently_selected = all_ids.issubset(st.session_state.rag_selected_videos)
        toggle_label = "❌ Deselect All" if all_currently_selected else "✅ Select All"

        if st.button(toggle_label, key="toggle_all_rag"):
            if all_currently_selected:
                st.session_state.rag_selected_videos = set()
                for video in all_videos:
                    st.session_state[f"video_checkbox_{video.id}"] = False
                for coll in collections:
                    st.session_state[f"coll_checkbox_{coll.id}"] = False
            else:
                st.session_state.rag_selected_videos = all_ids.copy()
                for video in all_videos:
                    st.session_state[f"video_checkbox_{video.id}"] = True
                for coll in collections:
                    st.session_state[f"coll_checkbox_{coll.id}"] = True
            st.rerun()

        # Show selected count
        selected_count = len(st.session_state.rag_selected_videos)
        st.caption(f"📊 Selected: {selected_count} / {total_videos} videos")

        st.markdown("---")

        # Collections
        if collections:
            st.markdown("### 📂 Collections")
            for collection in collections:
                with st.container():
                    # Collection-level checkbox
                    collection_video_ids = [v.id for v in collection.videos]
                    all_selected = all(vid in st.session_state.rag_selected_videos for vid in collection_video_ids)

                    col_selected = st.checkbox(
                        f"📂 {collection.title} ({len(collection.videos)} videos)",
                        value=all_selected,
                        key=f"coll_checkbox_{collection.id}"
                    )

                    # Update selection for all videos in collection
                    if col_selected:
                        st.session_state.rag_selected_videos.update(collection_video_ids)
                    else:
                        st.session_state.rag_selected_videos.difference_update(collection_video_ids)

                    # Show individual videos in collection (indented)
                    if collection.videos:
                        for video in sorted(collection.videos, key=lambda v: v.order_index or 0):
                            icon = _PLATFORM_ICONS.get(video.source_type, "▶️")
                            st.caption(f"  └─ {icon} {video.title[:60]}...")

            st.markdown("---")

        # Standalone Videos
        if all_videos:
            st.markdown("### 📹 Standalone Videos")
            for video in all_videos:
                icon = _PLATFORM_ICONS.get(video.source_type, "▶️")
                title = video.title[:78] + ("..." if len(video.title) > 78 else "")
                video_selected = st.checkbox(
                    f"{icon} {title}",
                    value=video.id in st.session_state.rag_selected_videos,
                    key=f"video_checkbox_{video.id}"
                )

                # Update selection
                if video_selected:
                    st.session_state.rag_selected_videos.add(video.id)
                else:
                    st.session_state.rag_selected_videos.discard(video.id)

    # Question input
    question = st.text_area(
        "Ask a question:",
        placeholder="Ask anything about your selected videos...",
        height=120,
        key="rag_question_input"
    )

    # Check if selected provider is available
    provider_available_rag = check_api_key_configured(selected_provider)

    # Search button
    if st.button("🔍 Search & Answer", type="primary", disabled=not question or not question.strip() or not provider_available_rag):
        if not question or not question.strip():
            st.warning("⚠️ Please enter a question")
            return

        # Check if any videos are selected
        if not st.session_state.rag_selected_videos:
            st.warning("⚠️ Please select at least one video in Search Scope")
            return

        with st.spinner("🔍 Searching relevant videos..."):
            try:
                # Call RAG pipeline with selected video IDs and language
                result = answer_question(
                    question=question.strip(),
                    top_k_videos=3,  # Default: search top 3 videos
                    top_k_segments=3,  # Default: 3 segments per video
                    provider=selected_provider,
                    model=selected_model,
                    min_video_score=0.3,
                    filter_video_ids=list(st.session_state.rag_selected_videos),
                    language=selected_language  # User's language choice
                )

                if result['status'] == 'no_results':
                    st.warning("⚠️ " + result['answer'])
                    st.info("💡 Try processing more videos on this topic or rephrase your question")
                    return

                # Display answer
                st.markdown("---")
                st.markdown("## 💡 Answer")

                # Show answer in a nice box
                # Replace large headings (# and ##) with smaller ones (###) for better display
                answer_text = result['answer']
                answer_text = answer_text.replace('\n# ', '\n### ')
                answer_text = answer_text.replace('\n## ', '\n### ')
                # Handle if answer starts with heading
                if answer_text.startswith('# '):
                    answer_text = '### ' + answer_text[2:]
                if answer_text.startswith('## '):
                    answer_text = '### ' + answer_text[3:]

                st.markdown(answer_text)

                # Display referenced videos
                st.markdown("---")
                st.markdown("## 📚 Referenced Videos")
                st.caption(f"Found {len(result['videos'])} relevant video(s)")

                for i, (video, score, match_info) in enumerate(result['videos'], 1):
                    with st.expander(f"{'🎯' if 'Keyword' in match_info else '💡'} Video {i}: {video.title}", expanded=(i == 1)):
                        # Match info
                        st.caption(f"**Relevance**: {match_info} (score: {score:.3f})")

                        # Metadata
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.caption(f"📺 {video.channel_name}")
                        with col2:
                            if video.duration_seconds:
                                duration_min = int(video.duration_seconds) // 60
                                duration_sec = int(video.duration_seconds) % 60
                                st.caption(f"⏱️ {duration_min}:{duration_sec:02d}")
                        with col3:
                            st.caption(f"📝 {video.transcript_source}")

                        # TL;DR
                        st.markdown("**Summary:**")
                        st.markdown(video.tldr[:300] + "..." if len(video.tldr) > 300 else video.tldr)

                        # Action buttons
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button(f"📄 View Full Summary", key=f"view_rag_{video.id}"):
                                st.session_state.selected_video_id = video.id
                                st.session_state._nav_redirect = "📚 Library"
                                st.rerun()
                        with col2:
                            platform = _PLATFORM_NAMES.get(video.source_type, "YouTube")
                            watch_icon = _PLATFORM_ICONS.get(video.source_type, "▶️")
                            st.markdown(f"[{watch_icon} Watch on {platform}]({video.source_url})")

                # Show context for debugging (optional)
                with st.expander("🔍 Debug: View Retrieved Context", expanded=False):
                    st.text(result.get('context', 'No context available'))

            except Exception as e:
                st.error(f"❌ Error generating answer: {str(e)}")
                st.exception(e)


def view_queue():
    """Render the Queue view showing all processing jobs."""
    st.title("📋 Processing Queue")
    st.caption("Videos are processed one at a time in the background. Close the tab and come back — jobs keep running.")

    # Clear finished jobs button
    if st.button("🧹 Clear Finished Jobs"):
        count = clear_finished_jobs()
        if count:
            st.toast(f"Cleared {count} finished job(s)")
        else:
            st.toast("No finished jobs to clear")
        st.rerun()

    @st.fragment(run_every=2)
    def _queue_live_panel():
        jobs = get_all_jobs(limit=50)

        if not jobs:
            st.info("No jobs yet. Add a video from ➕ New Video.")
            return

        for job in jobs:
            icon = "🅱️" if "bilibili" in job.url else "🎓" if "deeplearning.ai" in job.url else "▶️"
            job_label = f"{icon} {job.url}"
            if job.job_type == "generate_notes":
                job_label = f"📝 Generate Notes — {job.url}"
            with st.container(border=True):
                col1, col2 = st.columns([5, 1])
                with col1:
                    st.markdown(f"**{job_label}**")
                with col2:
                    st.caption(job.created_at.strftime("%H:%M:%S"))

                if job.status == "pending":
                    st.caption("🕐 Waiting in queue...")

                elif job.status == "processing":
                    steps = get_job_progress(job.id)
                    if steps:
                        for step in steps:
                            st.caption(step)
                    elif job.current_step:
                        # Fallback: tab was closed and reopened — show last DB-persisted step
                        st.caption(job.current_step)
                    else:
                        st.caption("⏳ Processing...")

                elif job.status == "completed":
                    st.success(job.current_step or "✅ Done")
                    col_a, col_b = st.columns([4, 1])
                    with col_a:
                        if job.result_video_id:
                            btn_label = "📝 View Notes" if job.job_type == "generate_notes" else "📄 View Summary"
                            if st.button(btn_label, key=f"view_job_{job.id}"):
                                st.session_state.selected_video_id = job.result_video_id
                                st.session_state._nav_redirect = "📚 Library"
                                st.rerun()
                    with col_b:
                        if st.button("🗑️", key=f"del_job_{job.id}"):
                            delete_job(job.id)
                            st.rerun()

                elif job.status == "failed":
                    st.error(f"❌ {job.error_message or 'Unknown error'}")
                    col_a, col_b = st.columns([4, 1])
                    with col_a:
                        if job.job_type == "generate_notes":
                            if st.button("🔄 Retry", key=f"retry_job_{job.id}"):
                                create_notes_job(job.target_video_id)
                                st.rerun()
                        else:
                            if st.button("🔄 Retry", key=f"retry_job_{job.id}"):
                                create_job(
                                    url=job.url,
                                    force_asr=job.force_asr,
                                    whisper_model=job.whisper_model,
                                    provider=job.provider,
                                    model=job.model,
                                )
                                st.rerun()
                    with col_b:
                        if st.button("🗑️", key=f"del_job_{job.id}"):
                            delete_job(job.id)
                            st.rerun()

    _queue_live_panel()


def main():
    """Main app entry point."""

    # Initialize database (creates tables if they don't exist)
    # This is idempotent - safe to call every time
    init_db()

    # Start background queue worker (idempotent — only starts once per process)
    start_queue_worker()

    # Check password
    if not check_password():
        return

    # Sidebar navigation
    st.sidebar.title("🎬 tldr-tube")
    st.sidebar.markdown("---")

    nav_options = ["➕ New Video", "➕ New Collection", "📚 Library", "📋 Queue", "🤖 Ask AI"]

    # Apply programmatic navigation redirect before the widget is instantiated
    if "_nav_redirect" in st.session_state:
        st.session_state["nav"] = st.session_state.pop("_nav_redirect")

    view = st.sidebar.radio(
        "Navigation",
        nav_options,
        label_visibility="collapsed",
        key="nav"
    )

    st.sidebar.markdown("---")
    st.sidebar.caption("YouTube & Bilibili video summarizer with timestamp-anchored summaries")

    # Route to view
    if view == "➕ New Video":
        view_new_video()
    elif view == "➕ New Collection":
        view_new_collection()
    elif view == "📚 Library":
        view_history()
    elif view == "📋 Queue":
        view_queue()
    elif view == "🤖 Ask AI":
        view_ask_ai()


if __name__ == "__main__":
    main()
