# Enhanced Media Generation CLI Tool & Web App

A powerful tool for generating videos and images using Google AI's latest models: **Veo 3.1** for video generation, **Imagen 4** for image generation, and **Gemini 3 Pro** for prompt enhancement. It provides both a command-line interface (CLI) and a web UI via Streamlit.

## Features

- 🎬 **Video Generation**: Create high-quality videos using Veo 3.1 (up to 8 seconds, 1080p)
- 🖼️ **Image Generation**: Generate stunning images using Imagen 4 (up to 4 images, 2K resolution)
- 🤖 **Prompt Enhancement**: Automatically improve prompts using Gemini 3 Pro
- 🔄 **Combination Mode**: Generate both videos and images from the same prompt
- 🎨 **Image-to-Video**: Generate an image first, then use it as reference for video creation
- ⏩ **Video Extension Chaining**: Automatically extend videos multiple times in one command (up to 5 extensions)
- 🖼️ **Reference Images**: Use your own images to guide video generation (up to 3)
- 📁 **Organized Output**: Timestamped subdirectories with metadata
- 🌐 **Web UI**: Interactive Streamlit web interface

## Installation

### Prerequisites
- Python 3.10+

### Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up your API key:**

   **Option 1: Using .env file (Recommended)**
   ```bash
   # Copy the example file
   cp .env.example .env

   # Edit .env and add your API key
   # GOOGLE_API_KEY=your-api-key-here
   ```

   **Option 2: Environment variable**
   ```bash
   export GOOGLE_API_KEY="your-api-key-here"
   ```

   **Option 3: Command line**
   ```bash
   python veo.py --api-key "your-api-key-here" --prompt "..."
   ```

   > **Note:** The tool checks for API keys in this order:
   > 1. `.env` file (if exists)
   > 2. Environment variables
   > 3. `.streamlit/secrets.toml` (for the web app)
   > 4. `--api-key` command line argument

## Web UI Usage (Streamlit)

You can run the web interface locally or deploy it to Streamlit Cloud.

**Run locally:**
```bash
streamlit run app.py
```

### Deploying to Streamlit Cloud

1. Push this repository to GitHub.
2. Go to [Streamlit Community Cloud](https://share.streamlit.io/) and log in.
3. Click "New app", select your repository, branch, and set the main file path to `app.py`.
4. In "Advanced settings", add your secrets:
   ```toml
   GOOGLE_API_KEY = "your-api-key-here"
   PASSWORD = "your-optional-password-here"
   ```
5. Deploy!

## CLI Usage

### Basic Examples

**Generate a video (default mode):**
```bash
python veo.py --prompt "A robot dancing in Times Square"
```

**Generate images only:**
```bash
python veo.py --mode image --prompt "Cyberpunk city at night" --image-count 2
```

**Generate both video and images:**
```bash
python veo.py --mode both --prompt "Cat playing piano"
```

**Quick video with fast model:**
```bash
python veo.py --prompt "Sunset over mountains" --video-model fast --video-duration 4
```

**Disable prompt enhancement:**
```bash
python veo.py --prompt "Detailed cinematic prompt here" --enhance-prompt false
```

### Advanced Examples

**High-quality video with custom settings:**
```bash
python veo.py \
  --prompt "A futuristic cityscape at golden hour" \
  --video-duration 8 \
  --video-resolution 1080p \
  --aspect-ratio 16:9 \
  --output-dir my_videos
```

**Multiple high-res images:**
```bash
python veo.py \
  --mode image \
  --prompt "Abstract art with vibrant colors" \
  --image-count 4 \
  --image-size 2K \
  --image-model ultra
```

**Image-to-Video (generate image, then video from it):**
```bash
python veo.py \
  --image-to-video \
  --prompt "A serene mountain landscape at sunset" \
  --image-count 1 \
  --video-duration 8
```

**Generate and extend a video (chained extensions):**
```bash
python veo.py \
  --prompt "A robot dancing in Times Square" \
  --extensions 2 \
  --video-duration 8
# Creates ~22 second video (8s initial + 7s + 7s extensions)
```

**Multiple prompts - one for each extension:**
```bash
# Use "|" to separate prompts (one per extension)
python veo.py \
  --prompt "A robot enters the stage in Times Square" \
  --extension-prompt "The robot waves to the crowd|The robot spins around|The robot takes a bow" \
  --extensions 3
```

**Use your own reference images for video:**
```bash
python veo.py \
  --reference-images style_ref.png,character_ref.png \
  --prompt "A character walking through the scene" \
  --video-duration 8
```

## Command-Line Options

### Required Options

| Option | Description |
|--------|-------------|
| `--prompt TEXT` | Media generation prompt (required) |

### Mode Selection

| Option | Values | Default | Description |
|--------|--------|---------|-------------|
| `--mode` | `video`, `image`, `both` | `video` | Generation mode |

### Prompt Enhancement

| Option | Values | Default | Description |
|--------|--------|---------|-------------|
| `--enhance-prompt` | `true`, `false` | `true` | Use Gemini 3 to enhance prompt |

### Video Options

| Option | Values | Default | Description |
|--------|--------|---------|-------------|
| `--video-duration` | `4`, `6`, `8` | `8` | Video duration in seconds |
| `--video-resolution` | `720p`, `1080p` | `1080p` | Video resolution |
| `--video-model` | `standard`, `fast` | `standard` | Video model variant |
| `--reference-images` | TEXT | - | Comma-separated paths to reference images (max 3) |
| `--extensions` | `0`, `1`, `2`, `3`, `4`, `5` | `0` | Number of times to extend video after generation (each adds ~7s) |
| `--extension-prompt` | TEXT | - | Optional prompt(s) for extensions. Use "\|" for multiple (one per extension) |
| `--image-to-video` | FLAG | `false` | Generate image first, then use as video reference |

### Image Options

| Option | Values | Default | Description |
|--------|--------|---------|-------------|
| `--image-count` | `1`, `2`, `3`, `4` | `4` | Number of images to generate |
| `--image-size` | `1K`, `2K` | `2K` | Image resolution |
| `--image-model` | `standard`, `ultra`, `fast` | `standard` | Image model variant |

### Common Options

| Option | Values | Default | Description |
|--------|--------|---------|-------------|
| `--aspect-ratio` | `1:1`, `3:4`, `4:3`, `9:16`, `16:9` | `16:9` | Aspect ratio for media |
| `--output-dir` | TEXT | `outputs` | Output directory name |
| `--api-key` | TEXT | - | Google AI API key |

## Output Structure

Each generation creates a timestamped subdirectory with all outputs:

```
outputs/
└── 2025-11-25_14-30-45/
    ├── metadata.json       # Generation parameters
    ├── prompt.txt          # Original and enhanced prompts
    ├── video_final.mp4     # Generated video (if video mode)
    └── image_1.png         # Generated images (if image mode)
```

## Troubleshooting

**API Key Not Found:**
```bash
export GOOGLE_API_KEY="your-api-key-here"
# or
python veo.py --api-key "your-api-key-here" --prompt "..."
```

**Generation Takes Too Long:**
- Try using `--video-model fast` for faster video generation
- Use shorter durations: `--video-duration 4`
- For images, try `--image-model fast`

**Content Blocked:**
- Modify your prompt to avoid potentially unsafe content
- The tool will display safety filter warnings
- No charges are incurred for blocked content

## License

This tool uses Google AI APIs. Please review Google's terms of service and pricing at:
- https://ai.google.dev/