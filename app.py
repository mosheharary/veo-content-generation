import tempfile
import time
import os
import shutil
from pathlib import Path

import streamlit as st
from google import genai
from google.genai import types

import base64
import uuid
import streamlit.components.v1 as components

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
    generate_extension_prompts,
    generate_image_prompt_json,
    generate_image_from_reference,
    generate_image_from_text,
    generate_continuation_prompt_json,
    generate_image_variation,
    compose_comics_pages,
    generate_comics_dialog,
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


def check_password():
    if st.session_state.get("authenticated", False):
        return True

    st.title("Veo 3.1 Media Generator")
    st.subheader("Sign in")

    with st.form("login_form"):
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in", use_container_width=True)

    if submitted:
        if password == st.secrets["PASSWORD"]:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password")

    return False


def check_api_key():
    if st.session_state.get("google_api_key"):
        return True

    st.title("Veo 3.1 Media Generator")
    st.subheader("Enter your Google API key")
    st.caption("Your key is used only for this session and is never stored.")

    with st.form("api_key_form"):
        api_key = st.text_input("Google API key", type="password", placeholder="AIza...")
        submitted = st.form_submit_button("Continue", use_container_width=True)

    if submitted:
        if api_key.strip():
            st.session_state["google_api_key"] = api_key.strip()
            st.rerun()
        else:
            st.error("Please enter a valid API key.")

    return False


if not check_password():
    st.stop()

if not check_api_key():
    st.stop()

# ── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Session")
    if st.button("Logout", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    if st.button("Change API key", use_container_width=True):
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
        mime = "image/png" if Path(reference_image_path).suffix.lower() == ".png" else "image/jpeg"
        status_widget.write(f"Uploading reference image...")
        uploaded = client.files.upload(
            file=str(reference_image_path),
            config=types.UploadFileConfig(
                mime_type=mime, display_name=Path(reference_image_path).name
            ),
        )
        kwargs["image"] = types.Image(gcs_uri=uploaded.uri)

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
        operation = client.operations.get(operation)

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
    client.files.download(file=video_file)

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
            raise RuntimeError("No videos generated in extension")

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
    placeholder="A majestic eagle soaring over snow-capped mountains at golden hour...",
    height=100,
)

uploaded_file = st.file_uploader(
    "Reference image (optional)",
    type=["png", "jpg", "jpeg"],
)

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

    col4, col5 = st.columns(2)
    extend_method = col4.selectbox(
        "Extend Method",
        ["image", "video"],
        index=0,
        help="'image' extracts the last frame and generates a new video. 'video' uses native extension (forces 720p).",
    )
    direct_image = col5.checkbox(
        "Direct Image",
        value=False,
        help="Pass reference image directly to Veo without restyling it first.",
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

generate_clicked = st.button(
    "Generate",
    type="primary",
    disabled=not prompt.strip(),
    use_container_width=True,
)

# ── Comics pre-generation approval ───────────────────────────────────────────

_is_comics = mode == "Image Only" and locals().get("style") != "all" and locals().get("comics", False)

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
        if st.button(f"✅ Confirm — generate {_total} images", type="primary", use_container_width=True):
            st.session_state.pop("comics_confirm_pending")
            st.session_state["comics_do_generate"] = True
            st.rerun()
    with _col_no:
        if st.button("✖ Cancel", use_container_width=True):
            st.session_state.pop("comics_confirm_pending", None)
            st.rerun()

_do_generate = (generate_clicked and not _is_comics) or st.session_state.pop("comics_do_generate", False)

# ── Generation flow ──────────────────────────────────────────────────────────

if _do_generate:
    client = get_client()
    cost_tracker = CostTracker()

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

        with st.status("Generating...", expanded=True) as status:
            if mode == "Video":
                ref_image_to_use = tmp_image_path
                if tmp_image_path and not direct_image:
                    status.write("Generating styled image from reference...")
                    ref_image_to_use = generate_image_from_reference(
                        client, prompt, tmp_image_path, out_dir, cost_tracker=cost_tracker
                    )

                video_file = generate_video_streamlit(
                    client=client,
                    prompt=prompt,
                    resolution=effective_resolution,
                    aspect_ratio=aspect_ratio,
                    reference_image_path=ref_image_to_use,
                    cost_tracker=cost_tracker,
                    status_widget=status,
                )

                if num_extensions > 0:
                    status.write(f"Generating {num_extensions} extension prompt(s)...")
                    ext_prompts = generate_extension_prompts(
                        client, prompt, num_extensions, cost_tracker=cost_tracker
                    )
                    generated_prompts.extend(ext_prompts)
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
                else:
                    final_video_path = out_dir / "video_final.mp4"
                    video_file.save(str(final_video_path))

                status.update(label="Done!", state="complete")

                st.session_state["video_bytes"] = final_video_path.read_bytes()

            else:  # Image Only
                if style_val == "all":
                    status.write(f"Generating images for all {len(STYLE_DEFINITIONS)} styles...")
                    all_style_paths = []
                    for s_name in STYLE_DEFINITIONS.keys():
                        s_dir = out_dir / s_name
                        s_dir.mkdir()
                        try:
                            status.write(f"Generating prompt for {s_name}...")
                            img_json = generate_image_prompt_json(
                                client, prompt, cost_tracker, style=s_name
                            )
                            generated_prompts.append(img_json)
                            if tmp_image_path:
                                status.write(f"Generating image for {s_name} (with reference)...")
                                img_path = generate_image_from_reference(
                                    client, img_json, tmp_image_path, s_dir, cost_tracker
                                )
                            else:
                                status.write(f"Generating image for {s_name}...")
                                img_path = generate_image_from_text(
                                    client,
                                    img_json,
                                    s_dir,
                                    filename="image.png",
                                    cost_tracker=cost_tracker,
                                )
                            all_style_paths.append(img_path)
                        except Exception as e:
                            status.write(f"Failed {s_name}: {e}")

                    status.update(label="Done!", state="complete")

                    images_data = []
                    for p in all_style_paths:
                        images_data.append(
                            {"name": p.parent.name, "bytes": p.read_bytes(), "ext": p.suffix}
                        )
                    st.session_state["images"] = images_data

                else:
                    all_image_paths = []
                    status.write(f"Generating prompt 1...")
                    prev_json = generate_image_prompt_json(
                        client, prompt, cost_tracker, style=style_val
                    )
                    generated_prompts.append(prev_json)

                    if tmp_image_path:
                        status.write(f"Generating image 1 (with reference)...")
                        prev_image_path = generate_image_from_reference(
                            client, prev_json, tmp_image_path, out_dir, cost_tracker
                        )
                        final_path = out_dir / ("image_1.png" if total_images > 1 else "image.png")
                        prev_image_path.rename(final_path)
                        prev_image_path = final_path
                    else:
                        status.write(f"Generating image 1...")
                        first_filename = "image_1.png" if total_images > 1 else "image.png"
                        prev_image_path = generate_image_from_text(
                            client,
                            prev_json,
                            out_dir,
                            filename=first_filename,
                            cost_tracker=cost_tracker,
                        )

                    all_image_paths.append(prev_image_path)

                    for i in range(2, total_images + 1):
                        status.write(f"Generating prompt {i}...")
                        next_json = generate_continuation_prompt_json(
                            client, prev_json, cost_tracker, style=style_val
                        )
                        generated_prompts.append(next_json)
                        status.write(f"Generating image {i}...")
                        img_path = generate_image_variation(
                            client,
                            next_json,
                            prev_image_path,
                            out_dir,
                            f"image_{i}.png",
                            cost_tracker,
                        )
                        prev_json = next_json
                        prev_image_path = img_path
                        all_image_paths.append(img_path)

                    if comics and len(all_image_paths) > 0:
                        status.write("Generating comics dialog...")
                        dialog_data = generate_comics_dialog(client, generated_prompts, cost_tracker=cost_tracker)
                        status.write("Composing comics pages...")
                        comic_pages = compose_comics_pages(all_image_paths, dialog_data, out_dir)
                        comics_data = [
                            {"name": p.name, "bytes": p.read_bytes(), "ext": p.suffix}
                            for p in comic_pages
                        ]
                        st.session_state["comics_images"] = comics_data

                    status.update(label="Done!", state="complete")

                    images_data = [
                        {"name": p.name, "bytes": p.read_bytes(), "ext": p.suffix}
                        for p in all_image_paths
                    ]
                    st.session_state["images"] = images_data

        st.session_state["cost"] = cost_tracker.total()
        st.session_state["last_prompt"] = prompt
        st.session_state["generated_prompts"] = generated_prompts

    except Exception as exc:
        st.error(f"Generation failed: {exc}")

    finally:
        # Clean up out_dir to prevent infinite growth
        if out_dir.exists():
            shutil.rmtree(out_dir, ignore_errors=True)

# ── Results display ──────────────────────────────────────────────────────────

if st.session_state.get("video_bytes") or st.session_state.get("images"):
    st.divider()
    col_result, col_clear = st.columns([6, 1])
    with col_result:
        st.subheader("Result")
    with col_clear:
        if st.button("🗑️ Clear", use_container_width=True):
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
                use_container_width=True,
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
            st.image(img["bytes"], caption=img["name"], use_container_width=True)
            col_d, col_s = st.columns(2)
            with col_d:
                st.download_button(
                    label="Download",
                    data=img["bytes"],
                    file_name=img["name"],
                    mime=f"image/{img['ext'].strip('.')}",
                    key=f"dl_comic_{img['name']}",
                    use_container_width=True,
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
                st.image(img["bytes"], caption=img["name"], use_container_width=True)
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
                        use_container_width=True,
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
