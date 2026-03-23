# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run CLI
python veo.py --prompt "Your prompt"

# Run web UI
streamlit run app.py
```

## Architecture

**Two interfaces, shared core logic:**

- `veo.py` — CLI entry point and all core logic (generation, polling, cost tracking, frame extraction)
- `app.py` — Streamlit web UI that imports from `veo.py` (`CostTracker`, model constants, utility functions)

**CLI subcommands** (`veo.py`):
- `generate` — main video/image generation (default subcommand)
- `list` — list files in Google Files API
- `download` — download generated files

**Key classes and functions in `veo.py`:**
- `CostTracker` — accumulates API costs; call `.add_video()`, `.add_text()`, `.add_image()`, `.print_summary()`
- `poll_operation()` — long-polls async Veo API operations (up to 12 min timeout)
- `generate_video()` — wraps Veo 3.1 API call
- `extend_video_chain()` — chains multiple video calls using last-frame extraction
- `extract_last_frame()` — OpenCV-based frame extraction for chaining
- `generate_extension_prompts()` — uses Gemini Pro to create continuation prompts

**Models:**
- `VEO_MODEL = "veo-3.1-generate-preview"` — video generation
- `TEXT_MODEL = "gemini-3.1-pro-preview"` — prompt enhancement
- `IMAGE_MODEL = "gemini-3.1-flash-image-preview"` — image generation

## Configuration

**API key resolution order:**
1. `.env` file (`GOOGLE_API_KEY`)
2. `GOOGLE_API_KEY` environment variable
3. `.streamlit/secrets.toml`
4. `--api-key` CLI flag

**Web UI secrets** (`.streamlit/secrets.toml`):
```toml
PASSWORD = "..."
GOOGLE_API_KEY = "..."
```

## Outputs

Each generation run creates `outputs/YYYY-MM-DD_HH-MM-SS/` containing:
- `metadata.json` — generation parameters
- `prompt_N.txt` — prompts used per segment
- `video_final.mp4` / `video_part_N.mp4` — generated videos
- `reference_image.png` / `image_N.png` — reference or generated images