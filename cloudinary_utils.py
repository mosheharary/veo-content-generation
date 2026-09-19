import cloudinary
import cloudinary.uploader
import streamlit as st
import os
import threading

# init_cloudinary() reads st.secrets, which only works from the main Streamlit
# script-run thread. Parallel image generation uploads from that same main
# thread (workers only generate images), but multiple images can each call
# upload_file_to_cloudinary() in quick succession, so configuration is guarded
# to run exactly once instead of re-touching st.secrets/os.environ every time.
_init_lock = threading.Lock()
_initialized = False

def init_cloudinary():
    global _initialized
    if _initialized:
        return
    with _init_lock:
        if _initialized:
            return
        cloudinary_url = ""
        try:
            cloudinary_url = st.secrets.get("CLOUDINARY_URL")
        except Exception:
            pass

        if not cloudinary_url:
            cloudinary_url = os.environ.get("CLOUDINARY_URL")

        if cloudinary_url:
            os.environ["CLOUDINARY_URL"] = cloudinary_url
            cloudinary.config(secure=True)
        _initialized = True

def upload_file_to_cloudinary(file_path, resource_type="auto"):
    """
    Uploads a file to Cloudinary and returns the secure URL.
    resource_type can be 'video', 'image', 'raw', or 'auto'
    """
    init_cloudinary()
    if not os.environ.get("CLOUDINARY_URL"):
        print("Warning: CLOUDINARY_URL not set. Skipping upload.")
        return None
        
    try:
        response = cloudinary.uploader.upload_large(str(file_path), resource_type=resource_type)
        return response.get("secure_url")
    except Exception as e:
        print(f"Cloudinary upload failed: {e}")
        return None
