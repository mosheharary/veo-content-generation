# Veo 3.1 Media Generator

A tool for generating videos and images using Google AI's latest models. Provides both a CLI (`veo.py`) and a Streamlit web UI (`app.py`).

**Models used:**
- `veo-3.1-generate-preview` — video generation
- `gemini-3.1-pro-preview` — prompt enhancement and storyboard continuation
- `gemini-3.1-flash-image-preview` — image generation and reference restyling

## Features

- **Video generation** — Veo 3.1, up to 8s, 720p / 1080p / 4k
- **Image generation** — storyboard sequences with style-locked continuation
- **Video extensions** — chain multiple segments using last-frame or native extension
- **Reference images** — restyle a photo and use it to anchor video generation
- **32 visual styles** — comics, anime, Pixar, film-noir, Studio Ghibli, baroque, surrealism, and more
- **Comics page composer** — lay out generated images into print-ready comics pages with AI-written dialog
- **Cost tracking** — live cost estimates and per-session totals

---

## Installation

```bash
pip install -r requirements.txt
```

### API Key

The CLI resolves the Google API key in this order:

1. `.env` file — `GOOGLE_API_KEY=your-key`
2. Environment variable — `export GOOGLE_API_KEY=your-key`
3. `.streamlit/secrets.toml` (web UI only)
4. Session entry prompt (web UI only — not stored)

---

## CLI — `veo.py`

### Commands

| Command | Description |
|---------|-------------|
| `generate` | Generate video or images (default — subcommand is optional) |
| `list` | List files stored in the Google Files API (expire after 48h) |
| `download <name>` | Download a file by name (e.g. `files/abc123`) |

---

### `generate` — Options

#### Core

| Option | Default | Description |
|--------|---------|-------------|
| `--prompt TEXT` | required | Video/image description |
| `--prompt-file PATH` | — | Read prompt from a text file |
| `--resolution` | `1080p` | `720p` · `1080p` · `4k` |
| `--aspect-ratio` | `16:9` | `16:9` · `9:16` |

> **Duration is determined by resolution:** `720p` → 4s · `1080p` / `4k` → 8s

#### Video Extension

| Option | Default | Description |
|--------|---------|-------------|
| `--extend N` | — | Generate N AI-written continuation prompts and extend the video N times |
| `--extend-method` | `image` | `image` — extracts last frame as reference, supports any resolution · `video` — native Veo extension, forces 720p |

#### Reference Image

| Option | Default | Description |
|--------|---------|-------------|
| `--image PATH` | — | Restyle this photo via Gemini Flash, then pass it to Veo as a reference |
| `--direct-image` | off | Skip the restyle step — pass the image directly to Veo (better face fidelity) |

#### Image-Only Mode

| Option | Default | Description |
|--------|---------|-------------|
| `--image-only` | off | Generate images instead of video |
| `--total-images N` | `1` | Generate N storyboard images — prompt 1 from idea, each subsequent prompt continues from the previous |
| `--style STYLE` | — | Visual style (see list below). Use `all` to generate one image per style |
| `--movie-title TITLE` | — | Movie or TV series name — required when `--style behind-the-scenes` |
| `--character-name NAME` | — | Famous person name — required when `--style celeb-selfie` |
| `--comics` | off | Compose all generated images into comics page(s) with AI-generated dialog |
| `--html` | off | Render generated images into a self-contained `images.html` file |

#### `download` — Options

| Option | Description |
|--------|-------------|
| `name` | File name from `list` output (e.g. `files/abc123`) |
| `--output PATH` | Save path (default: auto-named from file slug + extension) |

---

### CLI Examples

```bash
# Basic video
python veo.py --prompt "A cat walking through a sunlit garden"

# 4k video, portrait
python veo.py --prompt "A dancer performing ballet" --resolution 4k --aspect-ratio 9:16

# Extend video 3 times using last-frame method (retains resolution)
python veo.py --prompt "Ocean waves at sunset" --extend 3 --resolution 1080p

# Extend using native Veo extension (forces 720p)
python veo.py --prompt "Ocean waves at sunset" --extend 2 --extend-method video

# Video from reference photo (with restyle)
python veo.py --prompt "Futuristic cityscape at night" --image ./photo.png

# Video from reference photo (direct, no restyle — better for faces)
python veo.py --prompt "Walking through a park" --image ./photo.png --direct-image

# Single image
python veo.py --prompt "tiny workers building a frappuccino" --image-only

# 6-image storyboard in anime style
python veo.py --prompt "A space battle" --image-only --total-images 6 --style anime

# Anime storyboard composed into comics pages
python veo.py --prompt "A space battle" --image-only --total-images 6 --style anime --comics

# Generate one image per style (32 total)
python veo.py --prompt "A lone samurai" --image-only --style all

# Film noir image with HTML viewer
python veo.py --prompt "A detective in a dark alley" --image-only --style film-noir --html

# Celeb selfie (requires --character-name)
python veo.py --prompt "At a concert" --image-only --style celeb-selfie --character-name "Taylor Swift"

# Behind-the-scenes (requires --movie-title)
python veo.py --prompt "A chase scene" --image-only --style behind-the-scenes --movie-title "Breaking Bad"

# List files in Google Files API
python veo.py list

# Download a file
python veo.py download files/abc123 --output my_video.mp4
```

---

## Web UI — `app.py`

```bash
streamlit run app.py
```

### Authentication

On first launch the UI presents a **Login / Sign Up** screen:

- **Sign Up** — create an account (username ≥ 3 chars, password ≥ 6 chars)
- **Login** — authenticate with your credentials
- After login, you are prompted to enter your **Google API key** — it is used only for the current session and never stored.

### Navigation (sidebar)

| Item | Description |
|------|-------------|
| **Generator** | Main generation interface |
| **History** | View all past generations with media and cost |
| **Session Cost** | Running cost total for the current session |
| **Change API key** | Re-enter your Google API key |
| **Logout** | Clear session and return to login |

---

### Generator — Video Mode

Select **Video** from the mode toggle.

| Control | Options | Notes |
|---------|---------|-------|
| **Description** | Free text | Main prompt |
| **Reference image** | PNG / JPG upload | Optional — see below |
| **Resolution** | `720p` · `1080p` · `4k` | 1080p and 4k use 8s; 720p uses 4s |
| **Aspect ratio** | `16:9` · `9:16` | |
| **Extensions** | 0 – 20 | Number of continuation segments to append |
| **Extend Method** | `image` · `video` | `image` = last-frame extraction (any resolution); `video` = native Veo (forces 720p) |
| **Direct Image** | checkbox | Pass reference image straight to Veo without restyling |
| **Style** | None + 32 styles | Applies style via AI prompt enhancement before generation |

> The UI shows an **estimated cost** before generation and the **actual cost** afterward.

**Reference image + video flow:**
- Without **Direct Image**: the photo is restyled with Gemini Flash to match the prompt's aesthetic, then passed to Veo.
- With **Direct Image**: the original photo goes directly to Veo — better for face fidelity.

---

### Generator — Image Only Mode

Select **Image Only** from the mode toggle.

| Control | Options | Notes |
|---------|---------|-------|
| **Description** | Free text | Main idea — expanded into structured JSON prompt by Gemini Pro |
| **Reference image** | PNG / JPG upload | Optional — used as character/style anchor |
| **Style** | None · all · 32 styles | `all` generates one image per style (32 API calls) |
| **Total Images** | 1 – 20 | Storyboard sequence; each image continues from the previous |
| **Comics Page Layout** | checkbox | Compose images into comics pages with AI dialog |
| **Total Pages** | 1 – 10 | Only visible when Comics is checked — total_pages × panels_per_page = images generated |

**Comics confirmation:** When comics mode is selected, the UI asks for confirmation before starting (showing the total number of API calls).

---

### Results

After generation:

| Element | Description |
|---------|-------------|
| **Video player** | Inline playback |
| **Download button** | Save as `.mp4` |
| **Share button** | Native browser Web Share API (mobile-friendly) |
| **Images grid** | 3-column grid for image results |
| **Comics Pages** | Full-width composed comics page(s) |
| **Prompt used** | Expandable — shows original prompt and all generated JSON / extension prompts |
| **Clear** | Remove all results from the current view |

All results are automatically uploaded to **Cloudinary** and saved to the database linked to your user account. You can view them later under **History**.

---

## Visual Styles

Available for both CLI (`--style`) and web UI.

| Style | Description |
|-------|-------------|
| `comics` | Bold ink outlines, flat vivid colors, Ben-Day dot shading, Marvel/DC panel composition. Adds speech bubbles. |
| `pixar` | Pixar/Disney 3D CGI — warm vibrant lighting, rounded expressive characters, cinematic depth of field |
| `film-noir` | Black & white chiaroscuro, 1940s detective mood, venetian blind shadows, rain-slicked streets |
| `anime` | Japanese anime — cel-shaded, vibrant saturated colors, expressive large eyes, speed lines, manga composition |
| `watercolor` | Soft translucent brush strokes, bleeding ink edges, pastel tones, visible paper texture, impressionistic detail |
| `studio-ghibli` | Lush hand-painted backgrounds, whimsical characters, soft natural lighting, warm nostalgic atmosphere |
| `oil-painting` | Classical oil — rich impasto texture, dramatic chiaroscuro, deep pigments, Old Masters (Rembrandt/Caravaggio) |
| `retro-80s` | Synthwave/vaporwave — neon pinks, purples and cyans, chrome lettering, perspective grid, Miami Vice palette |
| `retro-50s` | 1950s Americana — warm Technicolor, atomic age optimism, halftone print, vintage ad illustration |
| `retro-70s` | 1970s retro — warm amber and avocado tones, grainy film look, bell-bottom culture, vintage Polaroid warmth |
| `cyberpunk` | Neon-soaked dystopian megacity, holographic ads, chrome implants, deep shadows with neon highlights, Blade Runner aesthetic |
| `fantasy` | High fantasy epic — sweeping grand landscapes, magical glowing elements, ornate armor, jewel tones, god-rays |
| `pixel-art` | Retro 8-bit/16-bit — visible square pixels, limited 16-32 color palette, hard edges, NES/SNES sprite aesthetic |
| `impressionist` | French Impressionist — loose visible brushstrokes, dappled sunlight, soft blended colors, Monet/Renoir plein air |
| `horror` | Cinematic psychological horror — desaturated palette, deep blacks, unsettling composition, grotesque details, James Wan/del Toro |
| `ukiyo-e` | Japanese ukiyo-e woodblock — flat bold color areas, strong black outlines, Hokusai/Hiroshige composition, indigo and vermillion palette |
| `claymation` | Claymation stop-motion — visible clay textures, fingerprint marks, wobbly organic forms, Aardman/Wallace & Gromit style |
| `art-nouveau` | Art Nouveau — flowing organic lines, ornate botanical borders, elegant elongated figures, Alphonse Mucha flat decorative style |
| `documentary` | Cinematic documentary — candid natural light, desaturated realistic tones, film grain, photojournalism National Geographic style |
| `low-poly` | Low-poly 3D geometric — flat-shaded triangular polygons, faceted crystal-like surfaces, bold color blocks, modern digital illustration |
| `sci-fi` | Epic sci-fi concept art — vast alien environments, glowing technology, hard-surface spacecraft, dramatic cosmic lighting, Syd Mead / Mass Effect |
| `sport` | Dynamic sports photography — freeze-frame peak action, motion blur, dramatic stadium lighting, high contrast, ESPN/Sports Illustrated editorial |
| `baroque` | 17th-century Baroque painting — dramatic diagonal composition, theatrical light shafts, rich jewel tones, ornate detail, Rubens/Velázquez grandeur |
| `pencil-sketch` | Detailed graphite/charcoal pencil drawing — cross-hatching, raw smudged shadows, white paper showing through, expressive hand-drawn energy |
| `stained-glass` | Medieval stained glass window art — bold lead-line outlines, saturated jewel-color panes, flat geometric forms, sacred/gothic light quality |
| `pop-art` | Andy Warhol / Roy Lichtenstein pop art — bold flat primary colors, Ben-Day halftone dots, silkscreen repetition, thick outlines, consumer-culture irony |
| `chinese-ink` | Traditional Chinese sumi-e ink wash painting — minimalist calligraphic brushstrokes, abundant negative space, misty mountains, zen tranquility |
| `isometric` | Clean isometric 3D illustration — precise 30° geometric perspective, flat pastel or bold colors, architectural cross-section, video-game diorama look |
| `surrealism` | Dalí / Magritte surrealist painting — photorealistic rendering of impossible dreamlike scenes, melting forms, impossible scale, uncanny juxtapositions |
| `golden-age` | Golden Age of American illustration — Norman Rockwell / N.C. Wyeth warm storytelling, rich earthy palette, heroic figures, magazine-cover narrative craft |
| `celeb-selfie` | Raw candid iPhone selfie with a famous person — photographic realism, phone flash, ISO grain. **Requires `--character-name`** |
| `behind-the-scenes` | Raw on-set snapshot — handheld camera, ISO grain, film crew visible, harsh mixed lighting for a named movie/TV show. **Requires `--movie-title`** |

---

## Output Structure (CLI)

Each generation run writes to `outputs/YYYY-MM-DD_HH-MM-SS/`:

```
outputs/
└── 2025-03-24_14-30-45/
    ├── prompt_0.txt            # Initial prompt
    ├── prompt_1.txt            # Extension prompt 1 (if --extend)
    ├── video_part_0.mp4        # Initial video segment
    ├── video_part_1.mp4        # Extension segment 1
    ├── video_final.mp4         # Final assembled video
    ├── reference_image.png     # Restyled reference (if --image)
    ├── image_prompt.json       # Structured JSON prompt (if --image-only)
    ├── image.png               # Generated image (single)
    ├── image_1.png             # Storyboard images (multi)
    ├── comics_page_1.png       # Comics layout pages (if --comics)
    └── images.html             # Self-contained viewer (if --html)
```

---

## Pricing (March 2026)

| Service | Rate |
|---------|------|
| Veo 720p / 1080p | $0.40 / second of video |
| Veo 4k | $0.60 / second of video |
| Gemini Pro (text) | $2.00 / 1M input tokens · $12.00 / 1M output tokens |
| Gemini Flash (image) | $0.50 / 1M input tokens · $60.00 / 1M image output tokens |

**Typical costs:**
- Single 4s 720p video: ~$1.60
- Single 8s 1080p video: ~$3.20
- Single 8s 4k video: ~$4.80
- One generated image: ~$0.01–$0.05 depending on complexity
- Each extension: adds one video segment cost

---

## Troubleshooting

**API key not found:**
```bash
export GOOGLE_API_KEY="your-key"
# or add to .env: GOOGLE_API_KEY=your-key
```

**Content blocked:** Rephrase your prompt to avoid content policy triggers. No charge is incurred for blocked requests.

**Generation timeout:** Video generation polls for up to 12 minutes (initial) / 6 minutes (extensions). Network blips are retried automatically up to 5 times.

**`--style all` fails:** Only supported with `--image-only`. Cannot be combined with `--total-images`.

**Native video extension forces 720p:** This is a Veo API constraint. Use `--extend-method image` to retain higher resolution.
