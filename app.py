import tempfile
import threading
import time
import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import streamlit as st
import db
import cloudinary_utils
from google import genai
from google.genai import types

import base64
import uuid
import streamlit.components.v1 as components

class TraceCollector:
    """Accumulates generation step traces in memory; bulk-inserts them to DB after commit."""

    def __init__(self):
        self._traces: list[dict] = []
        self._start = time.time()
        self._counter = 0
        self._lock = threading.Lock()

    def add(self, step_name: str, status: str, message: str = "", metadata: dict | None = None):
        with self._lock:
            self._counter += 1
            self._traces.append({
                "step_number":   self._counter,
                "step_name":     step_name,
                "status":        status,
                "message":       message,
                "metadata_json": metadata or {},
                "elapsed_sec":   round(time.time() - self._start, 2),
            })
        print(f"[TRACE] {step_name} - {status} ({message}) | metadata: {metadata or {}}")

    def flush(self, db_session, generation_id: str):
        """Bulk-insert all accumulated traces linked to generation_id."""
        for t in self._traces:
            db_session.add(db.GenerationTrace(generation_id=generation_id, **t))
        try:
            db_session.commit()
        except Exception as e:
            print(f"Error saving traces to DB: {e}")
        self._traces.clear()


def share_button(file_bytes, file_name, mime_type, button_text="Share"):
    b64_data = base64.b64encode(file_bytes).decode('utf-8')
    btn_id = "shareBtn_" + str(uuid.uuid4()).replace("-", "")
    
    html_code = f'''
    <style>body {{ margin: 0; padding: 0; overflow: hidden; }}</style>
    <div style="display: flex; justify-content: center; width: 100%;">
        <button id="{btn_id}" style="
            background-color: #ffffff;
            color: #31333F;
            border: 1px solid rgba(49, 51, 63, 0.2);
            padding: 0.25rem 0.75rem;
            font-size: 1rem;
            border-radius: 0.5rem;
            cursor: pointer;
            width: 100%;
            font-family: 'Source Sans Pro', sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s;
            height: 38.4px;
        " onmouseover="this.style.borderColor='rgb(255, 75, 75)'; this.style.color='rgb(255, 75, 75)';" 
           onmouseout="this.style.borderColor='rgba(49, 51, 63, 0.2)'; this.style.color='#31333F';">
            <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px;">
                <circle cx="18" cy="5" r="3"></circle>
                <circle cx="6" cy="12" r="3"></circle>
                <circle cx="18" cy="19" r="3"></circle>
                <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line>
                <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line>
            </svg>
            {button_text}
        </button>
    </div>
    
    <script>
    document.getElementById('{btn_id}').addEventListener('click', async () => {{
        const btn = document.getElementById('{btn_id}');
        const originalText = btn.innerHTML;
        btn.innerHTML = '...';
        
        setTimeout(async () => {{
            try {{
                const byteCharacters = atob('{b64_data}');
                const byteNumbers = new Array(byteCharacters.length);
                for (let i = 0; i < byteCharacters.length; i++) {{
                    byteNumbers[i] = byteCharacters.charCodeAt(i);
                }}
                const byteArray = new Uint8Array(byteNumbers);
                const blob = new Blob([byteArray], {{type: '{mime_type}'}});
                const file = new File([blob], '{file_name}', {{ type: '{mime_type}' }});
                
                const shareData = {{
                    files: [file],
                    title: 'Generated Media',
                }};
                
                if (window.parent.navigator.canShare && window.parent.navigator.canShare(shareData)) {{
                    await window.parent.navigator.share(shareData);
                }} else {{
                    alert('Sharing files is not supported on this browser/device.');
                }}
            }} catch (err) {{
                console.error('Share failed:', err);
            }}
            btn.innerHTML = originalText;
        }}, 50);
    }});
    </script>
    '''
    components.html(html_code, height=45)



from veo import (
    CostTracker,
    EXTENSION_RESOLUTION,
    MAX_POLL_SECONDS_EXTEND,
    MAX_POLL_SECONDS_VIDEO,
    POLL_INTERVAL,
    RESOLUTIONS_REQUIRING_8S,
    STYLE_DEFINITIONS,
    TEXT_MODEL,
    IMAGE_MODEL,
    VEO_MODEL,
    VEO_PRICE_PER_SEC,
    describe_image,
    generate_extension_prompts,
    generate_image_prompt_json,
    generate_video_prompt,
    generate_image_from_reference,
    generate_image_from_text,
    generate_continuation_prompt_json,
    generate_image_variation,
    compose_comics_pages,
    generate_comics_dialog,
    generate_images_parallel,
    IMAGE_CONCURRENCY,
    optimal_panels_per_page,
    extract_last_frame,
)

# ── Page config ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Veo 3.1 Media Generator",
    page_icon="🎬",
    layout="wide",
)

# ── Authentication ───────────────────────────────────────────────────────────



def login_ui():
    if st.session_state.get("authenticated", False):
        return True

    st.title("Veo 3.1 Media Generator")
    
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        st.subheader("Sign in")
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in", width='stretch')
            
            if submitted:
                db_session = db.get_session()
                try:
                    user = db.get_user_by_username(db_session, username)
                    if user and db.verify_password(password, user.password_hash):
                        st.session_state["authenticated"] = True
                        st.session_state["user_id"] = user.id
                        st.session_state["username"] = user.username
                        st.rerun()
                    else:
                        st.error("Incorrect username or password")
                finally:
                    db_session.close()

    with tab2:
        st.subheader("Create Account")
        with st.form("signup_form"):
            new_username = st.text_input("Choose Username")
            new_password = st.text_input("Choose Password", type="password")
            new_submitted = st.form_submit_button("Sign Up", width='stretch')
            
            if new_submitted:
                if len(new_username) < 3 or len(new_password) < 6:
                    st.error("Username must be at least 3 characters and password 6 characters.")
                else:
                    db_session = db.get_session()
                    try:
                        existing = db.get_user_by_username(db_session, new_username)
                        if existing:
                            st.error("Username already taken.")
                        else:
                            user = db.create_user(db_session, new_username, new_password)
                            st.success("Account created! You can now log in.")
                    finally:
                        db_session.close()

    return False




def check_api_key():
    if st.session_state.get("google_api_key"):
        return True

    # Match the documented resolution order (see CLAUDE.md): a key configured in
    # .streamlit/secrets.toml is used automatically, skipping the per-session prompt.
    try:
        secrets_key = st.secrets.get("GOOGLE_API_KEY")
    except Exception:
        secrets_key = None
    if secrets_key:
        st.session_state["google_api_key"] = secrets_key
        return True

    st.title("Veo 3.1 Media Generator")
    st.subheader("Enter your Google API key")
    st.caption("Your key is used only for this session and is never stored.")

    with st.form("api_key_form"):
        api_key = st.text_input("Google API key", type="password", placeholder="AIza...")
        submitted = st.form_submit_button("Continue", width='stretch')

    if submitted:
        if api_key.strip():
            st.session_state["google_api_key"] = api_key.strip()
            st.rerun()
        else:
            st.error("Please enter a valid API key.")

    return False


if not login_ui():
    st.stop()


if not check_api_key():
    st.stop()

# --- Main Navigation ---
nav_choice = st.sidebar.radio("Navigation", ["Generator", "History"])

if nav_choice == "History":
    st.title("My Generation History")
    
    db_session = db.get_session()
    try:
        user_id = st.session_state.get("user_id")
        if user_id:
            from db import Session, Generation

            def _generation_sort_key(gen):
                # A multi-image run commits its images out of completion order (they're
                # generated in parallel), so order the gallery by the stored frame index
                # instead of relying on insertion/created_at order. index may be an int
                # (storyboard frame), a style name, or a "comic_page_N" string.
                idx = (gen.metadata_json or {}).get("index")
                if isinstance(idx, int):
                    return (0, idx, gen.created_at)
                if isinstance(idx, str):
                    return (1, idx, gen.created_at)
                return (2, "", gen.created_at)

            sessions = db_session.query(Session).filter(Session.user_id == user_id).order_by(Session.created_at.desc()).all()
            if not sessions:
                st.info("You haven't generated anything yet.")

            for s in sessions:
                with st.expander(f"{s.session_name} - {s.created_at.strftime('%Y-%m-%d %H:%M')}"):
                    st.write(f"**Total Cost:** ${s.total_cost:.4f}")
                    gens = sorted(s.generations, key=_generation_sort_key)
                    if gens:
                        st.markdown(f"**Prompt:** {gens[0].prompt}")

                    video_gens = [g for g in gens if g.gen_type == 'video' and g.media_url]
                    for gen in video_gens:
                        st.video(gen.media_url)

                    # A multi-image run produces one Generation row per image; show them
                    # together in a grid instead of one-per-line so a 6-image run still
                    # reads as a single entry.
                    media_gens = [g for g in gens if g.gen_type != 'video' and g.media_url]
                    if media_gens:
                        cols = st.columns(3)
                        for i, gen in enumerate(media_gens):
                            cols[i % 3].image(gen.media_url)
                    st.divider()
    finally:
        db_session.close()
    
    st.stop()


# ── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Session")
    if st.button("Logout", width='stretch'):
        st.session_state.clear()
        st.rerun()

    if st.button("Change API key", width='stretch'):
        st.session_state.pop("google_api_key", None)
        st.rerun()

    key_preview = st.session_state.get("google_api_key", "")
    st.caption(f"API key: `{key_preview[:8]}...`" if key_preview else "No API key set")

    if st.session_state.get("cost") is not None:
        st.metric("Session Cost", f"${st.session_state['cost']:.4f}")

# ── Google client (session-scoped) ───────────────────────────────────────────


def get_client():
    return genai.Client(api_key=st.session_state["google_api_key"])


# ── Generation functions ─────────────────────────────────────────────────────


def generate_video_streamlit(
    client, prompt, resolution, aspect_ratio, reference_image_path, cost_tracker, status_widget
):
    duration = 8 if resolution in RESOLUTIONS_REQUIRING_8S else 4

    config = types.GenerateVideosConfig(
        duration_seconds=duration,
        resolution=resolution,
        aspect_ratio=aspect_ratio,
        number_of_videos=1,
    )

    video_prompt = prompt
    if reference_image_path:
        video_prompt = (
            "The reference image shows a private individual (not a public figure or celebrity), "
            "used with full consent for personal creative purposes. "
            "Use the provided photo as the exact visual reference. "
            "The subject must closely match the face shape, eye shape, nose, lips, and overall facial structure from the reference. "
            "Do not create a new person — replicate the look of the person in the uploaded image as faithfully as possible. "
            + prompt
        )

    kwargs = {"model": VEO_MODEL, "prompt": video_prompt, "config": config}

    if reference_image_path:
        status_widget.write(f"Reading reference image...")
        mime = "image/png" if Path(reference_image_path).suffix.lower() == ".png" else "image/jpeg"
        with open(str(reference_image_path), "rb") as f:
            image_bytes = f.read()
        kwargs["image"] = types.Image(image_bytes=image_bytes, mime_type=mime)

    status_widget.write("Starting generation request...")
    operation = client.models.generate_videos(**kwargs)

    progress_thresholds = [
        (15, "Analyzing prompt..."),
        (30, "Rendering initial frames..."),
        (60, "Processing video segments..."),
        (120, "Generating synchronized audio..."),
        (180, "Finalizing video composition..."),
        (240, "Almost there, finishing up..."),
    ]
    shown = set()
    start = time.time()

    while not getattr(operation, "done", False):
        elapsed = int(time.time() - start)

        for threshold, msg in progress_thresholds:
            if elapsed >= threshold and threshold not in shown:
                status_widget.write(f"⏳ {msg}")
                shown.add(threshold)

        if elapsed > MAX_POLL_SECONDS_VIDEO:
            raise TimeoutError("Timed out after 12 minutes")

        time.sleep(POLL_INTERVAL)
        for _attempt in range(5):
            try:
                operation = client.operations.get(operation)
                break
            except OSError as _net_err:
                status_widget.write(f"⚠️ Network blip polling status ({_net_err}), retrying in 10s…")
                print(f"[WARN] poll retry {_attempt + 1}/5: {_net_err}")
                time.sleep(10)
        else:
            raise RuntimeError("Lost network connectivity while polling — operation may still be running on the server")

    if getattr(operation, "error", None):
        raise RuntimeError(f"Operation failed: {operation.error}")

    response = getattr(operation, "response", None)
    videos = getattr(response, "generated_videos", None) if response else None
    if not videos:
        reason = (
            getattr(response, "error", None)
            or getattr(response, "message", None)
            or "No videos generated (possible content policy rejection)"
        )
        raise RuntimeError(str(reason))

    video_file = videos[0].video
    cost_tracker.add_video(duration, resolution)

    status_widget.write("Downloading video...")
    for _attempt in range(5):
        try:
            client.files.download(file=video_file)
            break
        except OSError as _net_err:
            status_widget.write(f"⚠️ Download blip ({_net_err}), retrying in 10s…")
            print(f"[WARN] download retry {_attempt + 1}/5: {_net_err}")
            time.sleep(10)
    else:
        raise RuntimeError("Failed to download video after 5 attempts — check your network")

    return video_file


def extend_video_streamlit(
    client,
    initial_video,
    extension_prompts,
    output_dir,
    resolution,
    aspect_ratio,
    extend_method,
    cost_tracker,
    status_widget,
):
    current_video = initial_video

    # Save the initial video first
    initial_video_path = output_dir / "video_part_0.mp4"
    current_video.save(str(initial_video_path))
    prev_video_path = initial_video_path

    for i, ext_prompt in enumerate(extension_prompts):
        status_widget.write(f"⏳ Extension {i + 1}/{len(extension_prompts)}: {ext_prompt[:80]}...")

        if extend_method == "image":
            ref_frame_path = output_dir / f"reference_frame_{i + 1}.png"
            status_widget.write(f"   Extracting last frame as reference...")
            extract_last_frame(prev_video_path, ref_frame_path)

            duration = 8 if resolution in RESOLUTIONS_REQUIRING_8S else 4

            with open(ref_frame_path, "rb") as f:
                image_bytes = f.read()

            operation = client.models.generate_videos(
                model=VEO_MODEL,
                prompt=ext_prompt,
                image=types.Image(image_bytes=image_bytes, mime_type="image/png"),
                config=types.GenerateVideosConfig(
                    number_of_videos=1,
                    resolution=resolution,
                    aspect_ratio=aspect_ratio,
                    duration_seconds=duration,
                ),
            )
            expected_cost_seconds = duration

        else:
            operation = client.models.generate_videos(
                model=VEO_MODEL,
                video=current_video,
                prompt=ext_prompt,
                config=types.GenerateVideosConfig(
                    number_of_videos=1,
                    resolution=EXTENSION_RESOLUTION,
                ),
            )
            expected_cost_seconds = 7

        shown = set()
        start = time.time()
        while not getattr(operation, "done", False):
            elapsed = int(time.time() - start)
            if elapsed > MAX_POLL_SECONDS_EXTEND:
                raise TimeoutError(f"Extension {i + 1} timed out after {MAX_POLL_SECONDS_EXTEND}s")
            if elapsed >= 30 and 30 not in shown:
                status_widget.write(f"   Rendering extension {i + 1}...")
                shown.add(30)
            time.sleep(POLL_INTERVAL)
            operation = client.operations.get(operation)

        if getattr(operation, "error", None):
            raise RuntimeError(f"Operation failed: {operation.error}")

        response = getattr(operation, "response", None)
        videos = getattr(response, "generated_videos", None) if response else None
        if not videos:
            rai_reasons = getattr(response, "rai_media_filtered_reasons", None) if response else None
            reason = (
                rai_reasons[0] if rai_reasons
                else getattr(response, "error", None)
                or getattr(response, "message", None)
                or "No videos generated (possible content policy rejection)"
            )
            print(f"[DEBUG] extension response: {response}")
            raise RuntimeError(f"Extension {i + 1} failed: {reason}")

        current_video = videos[0].video
        cost_tracker.add_video(
            expected_cost_seconds, resolution if extend_method == "image" else EXTENSION_RESOLUTION
        )

        status_widget.write(f"   Downloading intermediate video...")
        video_uri = current_video.uri
        client.files.download(file=current_video)

        prev_video_path = output_dir / f"video_part_{i + 1}.mp4"
        current_video.save(str(prev_video_path))

        if extend_method == "video" and i < len(extension_prompts) - 1:
            current_video = types.Video(uri=video_uri)

    return prev_video_path


# ── Main UI ──────────────────────────────────────────────────────────────────

st.title("🎬 Veo 3.1 Media Generator")

mode = st.radio("Mode", ["Video", "Image Only"], horizontal=True)

prompt = st.text_area(
    "Description",
    placeholder="A majestic eagle soaring over snow-capped mountains at golden hour... (optional when a reference image is provided)",
    height=100,
)

uploaded_file = st.file_uploader(
    "Reference image (optional)",
    type=["png", "jpg", "jpeg"],
)

movie_name_val = None

if mode == "Video":
    col1, col2, col3 = st.columns(3)
    resolution = col1.selectbox("Resolution", ["720p", "1080p", "4k"], index=1)
    aspect_ratio = col2.selectbox("Aspect ratio", ["16:9", "9:16"])
    num_extensions = col3.number_input(
        "Extensions",
        min_value=0,
        max_value=20,
        value=0,
        step=1,
        help="Number of segments to append.",
    )

    col4, col5, col6 = st.columns(3)
    extend_method = col4.selectbox(
        "Extend Method",
        ["video", "image"],
        index=0,
        help="'image' extracts the last frame and generates a new video. 'video' uses native extension (forces 720p).",
    )
    direct_image = col5.checkbox(
        "Direct Image",
        value=False,
        help="Pass reference image directly to Veo without restyling it first.",
    )
    video_style_options = ["None"] + list(STYLE_DEFINITIONS.keys())
    video_style = col6.selectbox(
        "Style",
        video_style_options,
        help="Apply a visual style to the video via AI prompt enhancement.",
    )
    video_style_val = None if video_style == "None" else video_style
    prompt_only = st.checkbox(
        "Enhance Prompt Only",
        value=False,
        help="Generate and display the enhanced prompt without running video generation.",
    )

    # Extensions force 720p if video method
    effective_resolution = (
        EXTENSION_RESOLUTION if (num_extensions > 0 and extend_method == "video") else resolution
    )

    duration = 8 if effective_resolution in RESOLUTIONS_REQUIRING_8S else 4
    ext_cost = (
        num_extensions
        * (duration if extend_method == "image" else 7)
        * VEO_PRICE_PER_SEC.get(
            effective_resolution if extend_method == "image" else EXTENSION_RESOLUTION, 0.40
        )
    )
    est_cost = duration * VEO_PRICE_PER_SEC.get(effective_resolution, 0.40) + ext_cost

    info_parts = [f"Initial Duration: **{duration}s**", f"Estimated cost: **${est_cost:.2f}**"]
    if num_extensions > 0 and extend_method == "video":
        info_parts.append(f"Resolution forced to **{EXTENSION_RESOLUTION}** for video extensions")
    st.info("  |  ".join(info_parts))

else:
    col1, col2, col3 = st.columns(3)
    style_options = ["None", "all"] + list(STYLE_DEFINITIONS.keys())
    style = col1.selectbox("Style", style_options)

    if style == "all":
        total_images = 1
        comics = False
    else:
        comics = col3.checkbox("Comics Page Layout", value=False)
        if comics:
            panels_per_page = optimal_panels_per_page()
            total_pages = col2.number_input("Total Pages", min_value=1, max_value=10, value=1, step=1)
            total_images = int(total_pages) * panels_per_page
        else:
            total_images = col2.number_input("Total Images", min_value=1, max_value=20, value=1, step=1)

    style_val = None if style == "None" else style

    movie_name_val = None
    character_name_val = None

    if style == "behind-the-scenes":
        _movie_input = st.text_input(
            "Movie / TV Series Name",
            placeholder="e.g. Titanic, Game of Thrones, Inception",
            help="Required for the Behind the Scenes style — specifies which film or show is being depicted on set.",
        )
        movie_name_val = _movie_input.strip() or None

    if style == "celeb-selfie":
        _character_input = st.text_input(
            "Famous Person / Character Name",
            placeholder="e.g. Elon Musk, Taylor Swift, Barack Obama",
            help="Required for the Celeb Selfie style — the famous person who will appear in the selfie.",
        )
        character_name_val = _character_input.strip() or None

    prompt_only = st.checkbox(
        "Enhance Prompt Only",
        value=False,
        help="Generate and display the enhanced image prompt without running image generation.",
    )

_bts_missing = locals().get("style") == "behind-the-scenes" and not movie_name_val
_celeb_missing = locals().get("style") == "celeb-selfie" and not character_name_val
generate_clicked = st.button(
    "Generate",
    type="primary",
    disabled=(not prompt.strip() and not uploaded_file) or _bts_missing or _celeb_missing,
    width='stretch',
)

# ── Comics pre-generation approval ───────────────────────────────────────────

_is_comics = mode == "Image Only" and locals().get("style") != "all" and locals().get("comics", False) and not locals().get("prompt_only", False)

if generate_clicked and _is_comics:
    st.session_state["comics_confirm_pending"] = total_images

if st.session_state.get("comics_confirm_pending") is not None:
    _total = st.session_state["comics_confirm_pending"]
    st.info(
        f"**Comics generation plan:** {_total} panel images will be generated "
        f"({_total} separate API calls). Ready to proceed?"
    )
    _col_yes, _col_no = st.columns(2)
    with _col_yes:
        if st.button(f"✅ Confirm — generate {_total} images", type="primary", width='stretch'):
            st.session_state.pop("comics_confirm_pending")
            st.session_state["comics_do_generate"] = True
            st.rerun()
    with _col_no:
        if st.button("✖ Cancel", width='stretch'):
            st.session_state.pop("comics_confirm_pending", None)
            st.rerun()

_do_generate = (generate_clicked and not _is_comics) or st.session_state.pop("comics_do_generate", False)

# ── Generation flow ──────────────────────────────────────────────────────────

if _do_generate:
    client = get_client()
    cost_tracker = CostTracker()
    tracer = TraceCollector()

    # Set up (only populated for Image Only / comics — see _persist_image below) so each
    # generated image can be uploaded to Cloudinary and committed to the DB as soon as it
    # exists, instead of waiting for the whole batch to finish.
    db_session = None
    parent_session_id = None
    persisted_generation_ids = []

    # Clean previous state
    generated_prompts = []
    for key in ["video_bytes", "images", "comics_images", "last_prompt", "generated_prompts"]:
        if key in st.session_state:
            del st.session_state[key]

    out_dir = Path(tempfile.mkdtemp(prefix="veo_streamlit_"))

    try:
        tmp_image_path = None
        if uploaded_file:
            suffix = ".png" if uploaded_file.type == "image/png" else ".jpg"
            tmp_image_path = out_dir / f"uploaded{suffix}"
            tmp_image_path.write_bytes(uploaded_file.read())

        if not prompt.strip() and tmp_image_path:
            with st.spinner("No prompt provided — auto-describing reference image..."):
                tracer.add("describe_image", "started")
                prompt = describe_image(client, tmp_image_path, cost_tracker=cost_tracker)
                tracer.add("describe_image", "completed", message=prompt[:300])
            st.info(f"Auto-generated description: {prompt}")

        with st.status("Generating...", expanded=True) as status:
            if prompt_only:
                if mode == "Video":
                    tracer.add("enhance_prompt", "started")
                    status.write("Enhancing video prompt...")
                    _po_enhanced = generate_video_prompt(
                        client, prompt, cost_tracker=cost_tracker, style=video_style_val
                    )
                    tracer.add("enhance_prompt", "completed",
                               message=_po_enhanced[:300],
                               metadata={"enhanced_prompt": _po_enhanced})
                    _po_label = "Enhanced Video Prompt"
                    _po_style = video_style_val
                else:
                    tracer.add("enhance_prompt", "started")
                    status.write("Enhancing image prompt...")
                    _po_enhanced = generate_image_prompt_json(
                        client, prompt, cost_tracker, style=style_val, movie_name=movie_name_val, character_name=character_name_val
                    )
                    tracer.add("enhance_prompt", "completed",
                               message=_po_enhanced[:300],
                               metadata={"enhanced_prompt": _po_enhanced})
                    _po_label = "Enhanced Image Prompt"
                    _po_style = style_val
                status.update(label="Done!", state="complete")
                _po_cost = cost_tracker.total() if hasattr(cost_tracker, "total") else 0.0
                st.session_state["cost"] = st.session_state.get("cost", 0.0) + _po_cost
                try:
                    import db as _db
                    _db_session = _db.get_session()
                    try:
                        _user_id = st.session_state.get("user_id")
                        if _user_id:
                            from datetime import datetime as _dt
                            _po_session = _db.Session(
                                user_id=_user_id,
                                session_name=f"Prompt Only - {_dt.now().strftime('%Y-%m-%d %H:%M')}",
                                total_cost=_po_cost,
                            )
                            _db_session.add(_po_session)
                            _db_session.flush()
                            _po_gen = _db.Generation(
                                session_id=_po_session.id,
                                gen_type="prompt_only",
                                prompt=prompt,
                                metadata_json={"enhanced_prompt": _po_enhanced, "mode": mode, "style": _po_style},
                                media_url=None,
                            )
                            _db_session.add(_po_gen)
                            _db_session.commit()
                            tracer.flush(_db_session, _po_gen.id)
                    except Exception as _e:
                        print(f"Error saving to DB: {_e}")
                    finally:
                        _db_session.close()
                except Exception as _e:
                    print(f"Error in DB save: {_e}")
                st.session_state["prompt_only_result"] = (_po_label, _po_enhanced)

            elif mode == "Video":
                tracer.add("generation_start", "started", metadata={
                    "mode": "video",
                    "prompt": prompt,
                    "resolution": effective_resolution,
                    "aspect_ratio": aspect_ratio,
                    "num_extensions": num_extensions,
                    "extend_method": extend_method,
                    "style": video_style_val,
                    "has_reference_image": tmp_image_path is not None,
                    "direct_image": direct_image,
                })

                ref_image_to_use = tmp_image_path
                if tmp_image_path and not direct_image:
                    tracer.add("style_reference_image", "started")
                    status.write("Generating styled image from reference...")
                    ref_image_to_use = generate_image_from_reference(
                        client, prompt, tmp_image_path, out_dir, cost_tracker=cost_tracker
                    )
                    tracer.add("style_reference_image", "completed",
                               metadata={"output_path": str(ref_image_to_use)})

                tracer.add("enhance_prompt", "started")
                status.write("Enhancing video prompt...")
                enhanced_prompt = generate_video_prompt(
                    client, prompt, cost_tracker=cost_tracker, style=video_style_val
                )
                tracer.add("enhance_prompt", "completed",
                           message=enhanced_prompt[:300],
                           metadata={"enhanced_prompt": enhanced_prompt})

                tracer.add("generate_initial_video", "started", metadata={
                    "resolution": effective_resolution,
                    "aspect_ratio": aspect_ratio,
                })
                video_file = generate_video_streamlit(
                    client=client,
                    prompt=enhanced_prompt,
                    resolution=effective_resolution,
                    aspect_ratio=aspect_ratio,
                    reference_image_path=ref_image_to_use,
                    cost_tracker=cost_tracker,
                    status_widget=status,
                )
                tracer.add("generate_initial_video", "completed")

                generated_prompts.append(enhanced_prompt)

                if num_extensions > 0:
                    tracer.add("generate_extension_prompts", "started",
                               metadata={"num_extensions": num_extensions})
                    status.write(f"Generating {num_extensions} extension prompt(s)...")
                    ext_prompts = generate_extension_prompts(
                        client, enhanced_prompt, num_extensions, cost_tracker=cost_tracker
                    )
                    tracer.add("generate_extension_prompts", "completed",
                               metadata={"prompts": ext_prompts})
                    generated_prompts.extend(ext_prompts)
                    for _i, _ep in enumerate(ext_prompts):
                        tracer.add(f"extend_video_{_i + 1}", "started",
                                   metadata={"prompt": _ep, "method": extend_method})
                    final_video_path = extend_video_streamlit(
                        client,
                        video_file,
                        ext_prompts,
                        out_dir,
                        effective_resolution,
                        aspect_ratio,
                        extend_method,
                        cost_tracker,
                        status,
                    )
                    for _i in range(len(ext_prompts)):
                        tracer.add(f"extend_video_{_i + 1}", "completed")
                else:
                    final_video_path = out_dir / "video_final.mp4"
                    video_file.save(str(final_video_path))

                status.update(label="Done!", state="complete")

                st.session_state["video_bytes"] = final_video_path.read_bytes()

                try:
                    # Calculate cost
                    total_cost = cost_tracker.total() if hasattr(cost_tracker, 'total') else 0.0
                    st.session_state["cost"] = st.session_state.get("cost", 0.0) + total_cost

                    # Upload to Cloudinary
                    tracer.add("upload_cloudinary", "started")
                    import cloudinary_utils
                    cloud_url = cloudinary_utils.upload_file_to_cloudinary(final_video_path, resource_type="video")
                    tracer.add("upload_cloudinary", "completed", metadata={"url": cloud_url})

                    # Save to DB
                    import db
                    db_session = db.get_session()
                    try:
                        user_id = st.session_state.get("user_id")
                        if user_id:
                            from datetime import datetime
                            session_name = f"Video Gen - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                            new_session = db.Session(user_id=user_id, session_name=session_name, total_cost=total_cost)
                            db_session.add(new_session)
                            db_session.flush()

                            metadata = {
                                "prompts": generated_prompts,
                                "resolution": resolution,
                                "aspect_ratio": aspect_ratio,
                                "total_images": 1,
                                "style": video_style_val,
                                "enhanced_prompt": enhanced_prompt,
                            }

                            new_gen = db.Generation(
                                session_id=new_session.id,
                                gen_type='video',
                                prompt=prompt,
                                metadata_json=metadata,
                                media_url=cloud_url
                            )
                            db_session.add(new_gen)
                            db_session.commit()
                            tracer.add("save_to_db", "completed",
                                       metadata={"generation_id": new_gen.id, "total_cost": total_cost})
                            tracer.add("generation_complete", "completed",
                                       metadata={"total_cost": total_cost})
                            tracer.flush(db_session, new_gen.id)
                    except Exception as e:
                        print(f"Error saving to DB: {e}")
                    finally:
                        db_session.close()
                except Exception as e:
                    print(f"Error in upload/save: {e}")


            else:  # Image Only
                tracer.add("generation_start", "started", metadata={
                    "mode": "image",
                    "prompt": prompt,
                    "style": style_val,
                    "total_images": total_images,
                    "comics": comics,
                    "has_reference_image": tmp_image_path is not None,
                })

                # Phase 0 — set up Cloudinary + a parent DB Session row up front so every
                # image generated below can be uploaded and committed to its own Generation
                # row as soon as it exists, instead of waiting for the whole batch to finish.
                # A DB/Cloudinary outage here must not block generation itself.
                try:
                    cloudinary_utils.init_cloudinary()
                    user_id = st.session_state.get("user_id")
                    if user_id:
                        db_session = db.get_session()
                        from datetime import datetime
                        session_name = (
                            f"{'Comics' if _is_comics else 'Image'} Gen - "
                            f"{datetime.now().strftime('%Y-%m-%d %H:%M')}"
                        )
                        parent_db_session = db.Session(
                            user_id=user_id, session_name=session_name, total_cost=0.0
                        )
                        db_session.add(parent_db_session)
                        db_session.flush()
                        parent_session_id = parent_db_session.id
                except Exception as e:
                    print(f"Error setting up persistence: {e}")
                    db_session = None
                    parent_session_id = None

                def _persist_image(index, path, gen_type="image", extra_metadata=None):
                    """Upload one image to Cloudinary and commit its own Generation row
                    immediately. Runs on the main thread only (Cloudinary/DB/Streamlit are
                    not thread-safe). A failure here is logged and traced but never aborts
                    the rest of the batch."""
                    if not (db_session and parent_session_id):
                        return None
                    try:
                        cloud_url = cloudinary_utils.upload_file_to_cloudinary(
                            str(path), resource_type="image"
                        )
                        if not cloud_url:
                            tracer.add(f"upload_image_{index}", "failed",
                                       message="Cloudinary upload returned no URL")
                            return None
                        tracer.add(f"upload_image_{index}", "completed", metadata={"url": cloud_url})
                        metadata = {"index": index, "total_images": total_images, "aspect_ratio": "16:9"}
                        if extra_metadata:
                            metadata.update(extra_metadata)
                        new_gen = db.Generation(
                            session_id=parent_session_id,
                            gen_type=gen_type,
                            prompt=prompt,
                            metadata_json=metadata,
                            media_url=cloud_url,
                        )
                        db_session.add(new_gen)
                        db_session.commit()
                        persisted_generation_ids.append(new_gen.id)
                        tracer.add(f"save_to_db_{index}", "completed",
                                   metadata={"generation_id": new_gen.id})
                        return cloud_url
                    except Exception as e:
                        print(f"Error persisting image {index}: {e}")
                        tracer.add(f"persist_image_{index}", "failed", message=str(e))
                        return None

                if style_val == "all":
                    style_names = [
                        s for s in STYLE_DEFINITIONS.keys()
                        if not (STYLE_DEFINITIONS.get(s, {}).get("requires_movie_name") or
                                STYLE_DEFINITIONS.get(s, {}).get("requires_character_name"))
                    ]
                    for s_name in STYLE_DEFINITIONS.keys():
                        if s_name not in style_names:
                            status.write(f"Skipping {s_name} — requires additional parameter")

                    # Phase 1 — one prompt per style, sequential (cheap text calls).
                    style_prompts = {}
                    for s_name in style_names:
                        s_dir = out_dir / s_name
                        s_dir.mkdir()
                        try:
                            tracer.add(f"generate_prompt_{s_name}", "started")
                            status.write(f"Generating prompt for {s_name}...")
                            img_json = generate_image_prompt_json(
                                client, prompt, cost_tracker, style=s_name
                            )
                            style_prompts[s_name] = img_json
                            tracer.add(f"generate_prompt_{s_name}", "completed")
                        except Exception as e:
                            tracer.add(f"generate_prompt_{s_name}", "failed", message=str(e))
                            status.write(f"Failed to generate prompt for {s_name}: {e}")

                    # Phase 2 — fan out image generation across styles, IMAGE_CONCURRENCY at
                    # a time. Each style has its own directory, so filenames never collide.
                    # Uploaded + committed to its own Generation row as soon as it lands.
                    def _generate_one_style(s_name, img_json):
                        s_dir = out_dir / s_name
                        if tmp_image_path:
                            return generate_image_from_reference(
                                client, img_json, tmp_image_path, s_dir, cost_tracker
                            )
                        return generate_image_from_text(
                            client, img_json, s_dir, filename="image.png", cost_tracker=cost_tracker,
                        )

                    all_style_paths = []
                    if style_prompts:
                        status.write(
                            f"Generating {len(style_prompts)} images "
                            f"({min(IMAGE_CONCURRENCY, len(style_prompts))} at a time)..."
                        )
                        with ThreadPoolExecutor(max_workers=IMAGE_CONCURRENCY) as executor:
                            future_to_style = {
                                executor.submit(_generate_one_style, s_name, img_json): s_name
                                for s_name, img_json in style_prompts.items()
                            }
                            for future in as_completed(future_to_style):
                                s_name = future_to_style[future]
                                try:
                                    img_path = future.result()
                                except Exception as e:
                                    tracer.add(f"generate_image_{s_name}", "failed", message=str(e))
                                    status.write(f"Failed {s_name}: {e}")
                                    continue
                                tracer.add(f"generate_image_{s_name}", "completed",
                                           metadata={"output_path": str(img_path)})
                                status.write(f"{s_name} done — uploading...")
                                all_style_paths.append(img_path)
                                generated_prompts.append(style_prompts[s_name])
                                _persist_image(s_name, img_path, extra_metadata={"style": s_name})

                    status.update(label="Done!", state="complete")

                    images_data = []
                    for p in all_style_paths:
                        images_data.append(
                            {"name": p.parent.name, "bytes": p.read_bytes(), "ext": p.suffix}
                        )
                    st.session_state["images"] = images_data

                else:
                    # Phase 1 — prompts, sequential. Prompt i continues prompt i-1 so the
                    # storyboard reads as one narrative; these are cheap text-only calls.
                    prompt_jsons = {}
                    tracer.add("generate_prompt_1", "started")
                    status.write("Generating prompt 1...")
                    prev_json = generate_image_prompt_json(
                        client, prompt, cost_tracker, style=style_val, movie_name=movie_name_val, character_name=character_name_val
                    )
                    prompt_jsons[1] = prev_json
                    tracer.add("generate_prompt_1", "completed")

                    for i in range(2, total_images + 1):
                        tracer.add(f"generate_prompt_{i}", "started")
                        status.write(f"Generating prompt {i}...")
                        next_json = generate_continuation_prompt_json(
                            client, prev_json, cost_tracker, style=style_val, movie_name=movie_name_val, character_name=character_name_val
                        )
                        prompt_jsons[i] = next_json
                        tracer.add(f"generate_prompt_{i}", "completed")
                        prev_json = next_json

                    # Phase 2 — anchor image (image 1), sequential; persisted immediately.
                    # It becomes the shared style/character reference for images 2..N.
                    tracer.add("generate_image_1", "started",
                               metadata={"with_reference": tmp_image_path is not None})
                    if tmp_image_path:
                        status.write("Generating image 1 (with reference)...")
                        anchor_path = generate_image_from_reference(
                            client, prompt_jsons[1], tmp_image_path, out_dir, cost_tracker
                        )
                        final_path = out_dir / ("image_1.png" if total_images > 1 else "image.png")
                        anchor_path.rename(final_path)
                        anchor_path = final_path
                    else:
                        status.write("Generating image 1...")
                        first_filename = "image_1.png" if total_images > 1 else "image.png"
                        anchor_path = generate_image_from_text(
                            client,
                            prompt_jsons[1],
                            out_dir,
                            filename=first_filename,
                            cost_tracker=cost_tracker,
                        )
                    tracer.add("generate_image_1", "completed", metadata={"output_path": str(anchor_path)})
                    status.write("Image 1 done — uploading...")
                    results = {1: anchor_path}
                    _persist_image(1, anchor_path)

                    # Phase 3 — images 2..N, fanned out IMAGE_CONCURRENCY at a time against
                    # the shared anchor image. Each is uploaded/committed as soon as it lands,
                    # while the rest of the batch is still generating.
                    if total_images > 1:
                        status.write(
                            f"Generating images 2-{total_images} "
                            f"({min(IMAGE_CONCURRENCY, total_images - 1)} at a time)..."
                        )
                        for idx, img_path, err in generate_images_parallel(
                            client, [(i, prompt_jsons[i]) for i in range(2, total_images + 1)],
                            anchor_path, out_dir, cost_tracker=cost_tracker, max_workers=IMAGE_CONCURRENCY,
                        ):
                            if err:
                                tracer.add(f"generate_image_{idx}", "failed", message=str(err))
                                status.write(f"Image {idx} failed: {err}")
                                continue
                            tracer.add(f"generate_image_{idx}", "completed",
                                       metadata={"output_path": str(img_path)})
                            status.write(f"Image {idx} done — uploading...")
                            results[idx] = img_path
                            _persist_image(idx, img_path)

                    # Phase 4 — restore narrative order (parallel completion scrambles it)
                    # before anything order-sensitive: comics composition, gallery display.
                    all_image_paths = [results[i] for i in sorted(results)]
                    generated_prompts = [prompt_jsons[i] for i in sorted(results)]

                    if comics and len(all_image_paths) > 0:
                        tracer.add("generate_comics_dialog", "started")
                        status.write("Generating comics dialog...")
                        dialog_data = generate_comics_dialog(client, generated_prompts, cost_tracker=cost_tracker)
                        tracer.add("generate_comics_dialog", "completed")
                        tracer.add("compose_comics_pages", "started")
                        status.write("Composing comics pages...")
                        comic_pages = compose_comics_pages(all_image_paths, dialog_data, out_dir, style=style_val)
                        tracer.add("compose_comics_pages", "completed",
                                   metadata={"num_pages": len(comic_pages)})
                        comics_data = [
                            {"name": p.name, "bytes": p.read_bytes(), "ext": p.suffix}
                            for p in comic_pages
                        ]
                        st.session_state["comics_images"] = comics_data
                        for page_idx, p in enumerate(comic_pages, start=1):
                            status.write(f"Comic page {page_idx} done — uploading...")
                            _persist_image(f"comic_page_{page_idx}", p, gen_type="comics")

                    status.update(label="Done!", state="complete")

                    images_data = [
                        {"name": p.name, "bytes": p.read_bytes(), "ext": p.suffix}
                        for p in all_image_paths
                    ]
                    st.session_state["images"] = images_data


        st.session_state["cost"] = cost_tracker.total()
        st.session_state["last_prompt"] = prompt
        st.session_state["generated_prompts"] = generated_prompts

        # Image/comics generations were already uploaded to Cloudinary and committed to
        # their own Generation rows one at a time as each one completed (see
        # _persist_image above) — no batch upload/save step needed here anymore. Just
        # finalize the parent Session's total cost and flush the accumulated traces.
        if (mode == "Image Only" or _is_comics) and db_session and parent_session_id:
            try:
                total_cost = st.session_state["cost"]
                db_session.query(db.Session).filter(db.Session.id == parent_session_id).update(
                    {"total_cost": total_cost}
                )
                db_session.commit()
                tracer.add("generation_complete", "completed", metadata={"total_cost": total_cost})
                if persisted_generation_ids:
                    tracer.flush(db_session, persisted_generation_ids[-1])
            except Exception as e:
                print(f"Error finalizing session cost: {e}")
            finally:
                db_session.close()

    except Exception as exc:
        tracer.add("generation_failed", "failed", message=str(exc))
        st.error(f"Generation failed: {exc}")

    finally:
        # Clean up out_dir to prevent infinite growth
        if out_dir.exists():
            shutil.rmtree(out_dir, ignore_errors=True)

# ── Prompt-only result display ───────────────────────────────────────────────

if st.session_state.get("prompt_only_result"):
    _po_label, _po_text = st.session_state["prompt_only_result"]
    st.divider()
    col_result, col_clear = st.columns([6, 1])
    with col_result:
        st.subheader(_po_label)
    with col_clear:
        if st.button("🗑️ Clear", key="clear_prompt_only", width='stretch'):
            st.session_state.pop("prompt_only_result", None)
            st.rerun()
    st.text_area("", value=_po_text, height=300, key="prompt_only_display")

# ── Results display ──────────────────────────────────────────────────────────

if st.session_state.get("video_bytes") or st.session_state.get("images"):
    st.divider()
    col_result, col_clear = st.columns([6, 1])
    with col_result:
        st.subheader("Result")
    with col_clear:
        if st.button("🗑️ Clear", width='stretch'):
            for key in ["video_bytes", "images", "comics_images", "last_prompt", "generated_prompts", "cost"]:
                st.session_state.pop(key, None)
            st.rerun()

    if st.session_state.get("video_bytes"):
        st.video(st.session_state["video_bytes"])

        col_a, col_b, col_c = st.columns([2, 1, 1])
        with col_a:
            st.metric("Actual Cost", f"${st.session_state['cost']:.4f}")
        with col_b:
            st.download_button(
                label="Download",
                data=st.session_state["video_bytes"],
                file_name="veo_video.mp4",
                mime="video/mp4",
                width='stretch',
            )
        with col_c:
            share_button(
                file_bytes=st.session_state["video_bytes"],
                file_name="veo_video.mp4",
                mime_type="video/mp4"
            )

    if st.session_state.get("comics_images"):
        st.subheader("Comics Pages")
        for img in st.session_state["comics_images"]:
            st.image(img["bytes"], caption=img["name"], width='stretch')
            col_d, col_s = st.columns(2)
            with col_d:
                st.download_button(
                    label="Download",
                    data=img["bytes"],
                    file_name=img["name"],
                    mime=f"image/{img['ext'].strip('.')}",
                    key=f"dl_comic_{img['name']}",
                    width='stretch',
                )
            with col_s:
                share_button(
                    file_bytes=img["bytes"],
                    file_name=img["name"],
                    mime_type=f"image/{img['ext'].strip('.')}"
                )
            st.divider()

    if st.session_state.get("images"):
        st.subheader("Generated Images")

        images = st.session_state["images"]
        # Display in a grid
        cols = st.columns(3)
        for i, img in enumerate(images):
            with cols[i % 3]:
                st.image(img["bytes"], caption=img["name"], width='stretch')
                col_d, col_s = st.columns(2)
                with col_d:
                    st.download_button(
                        label="Download",
                        data=img["bytes"],
                        file_name=(
                            img["name"]
                            if img["name"].endswith(img["ext"])
                            else f"{img['name']}{img['ext']}"
                        ),
                        mime=f"image/{img['ext'].strip('.')}",
                        key=f"dl_img_{i}_{img['name']}",
                        width='stretch',
                    )
                with col_s:
                    share_button(
                        file_bytes=img["bytes"],
                        file_name=(
                            img["name"]
                            if img["name"].endswith(img["ext"])
                            else f"{img['name']}{img['ext']}"
                        ),
                        mime_type=f"image/{img['ext'].strip('.')}"
                    )

        if not st.session_state.get("video_bytes"):
            st.metric("Actual Cost", f"${st.session_state['cost']:.4f}")

    if st.session_state.get("last_prompt"):
        with st.expander("Prompt used"):
            st.markdown("**Original Prompt:**")
            st.write(st.session_state["last_prompt"])
            if st.session_state.get("generated_prompts"):
                st.markdown("**Generated JSON / Extension Prompts:**")
                for i, gp in enumerate(st.session_state["generated_prompts"], 1):
                    st.markdown(f"*Prompt {i}:*")
                    if "{" in gp:
                        st.code(gp, language="json")
                    else:
                        st.info(gp)
