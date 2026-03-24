#!/usr/bin/env python3
"""
Veo 3.1 Video Generation CLI
Simple 5-parameter interface for generating videos with optional extensions and image references.
"""

import argparse
import base64
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# Models
TEXT_MODEL = "gemini-3.1-pro-preview"
IMAGE_MODEL = "gemini-3.1-flash-image-preview"
VEO_MODEL = "veo-3.1-generate-preview"

# Style definitions — each style has prompt injections for initial and continuation frames.
# "comics" also includes a dialog_field that asks the IMAGE model to render speech bubbles.
STYLE_DEFINITIONS = {
    "comics": {
        "description": "Bold ink outlines, flat vivid colors, Ben-Day dot shading, Marvel/DC panel composition. Adds speech bubbles and dialog.",
        "init_note": (
            "The image MUST be in a bold comic book art style: strong ink outlines, flat vivid colors, "
            "Ben-Day dot shading, dynamic action poses, dramatic panel-worthy composition. "
            'Set "aesthetics.style" to "comic book illustration, bold ink outlines, flat colors, Marvel/DC style" '
            "and reflect this throughout all other fields.\n"
        ),
        "cont_note": (
            "Maintain the comic book art style: bold ink outlines, flat vivid colors, dynamic composition.\n"
            "Include a 'dialog' field with new dialog that advances the story — "
            '{"speaker": "Name", "text": "SHORT PUNCHY LINE IN CAPS", "bubble_type": "speech"|"shout"|"whisper"} '
            "or a caption — rendered as a speech bubble / caption box drawn inside the panel art.\n"
        ),
        "dialog_field": (
            '    "dialog": if characters are present include {"speaker": "Name", "text": "SHORT PUNCHY LINE IN CAPS", '
            '"bubble_type": "speech"|"shout"|"whisper"} — the image must visibly render this as a speech bubble '
            "drawn in classic comics lettering style directly inside the panel art. "
            'If no characters, use {"caption": "BRIEF NARRATION IN CAPS"} rendered as a yellow caption box.\n'
        ),
    },
    "pixar": {
        "description": "Pixar/Disney 3D CGI animation — warm vibrant lighting, rounded expressive characters, cinematic depth of field.",
        "init_note": (
            "The image MUST be in a Pixar/Disney 3D CGI animation style: warm vibrant lighting, "
            "rounded expressive characters with exaggerated features, cinematic depth of field, "
            'polished surface shading, rich saturated colors. Set "aesthetics.style" to '
            '"Pixar 3D CGI animation, warm lighting, expressive characters, cinematic" '
            "and reflect this throughout all other fields.\n"
        ),
        "cont_note": (
            "Maintain the Pixar 3D CGI animation style: warm vibrant lighting, "
            "rounded expressive characters, cinematic depth of field.\n"
        ),
        "dialog_field": "",
    },
    "film-noir": {
        "description": "Black & white chiaroscuro shadows, 1940s detective mood, venetian blind patterns, rain-slicked streets.",
        "init_note": (
            "The image MUST be in a classic film noir style: black and white or deep sepia tones, "
            "dramatic high-contrast chiaroscuro shadows, moody atmospheric lighting, "
            "1940s detective aesthetic, venetian blind shadow patterns, rain-slicked streets. "
            'Set "aesthetics.style" to "film noir, black and white, high contrast shadows, 1940s detective" '
            "and reflect this throughout all other fields.\n"
        ),
        "cont_note": (
            "Maintain the film noir style: black and white, dramatic shadows, moody 1940s atmosphere.\n"
        ),
        "dialog_field": "",
    },
    "anime": {
        "description": "Japanese anime — cel-shaded illustration, vibrant saturated colors, expressive large eyes, speed lines, manga composition.",
        "init_note": (
            "The image MUST be in a Japanese anime style: cel-shaded illustration, vibrant saturated colors, "
            "expressive large eyes, dynamic speed lines and motion blur, manga-inspired composition, "
            'bold outlines. Set "aesthetics.style" to "Japanese anime, cel-shaded, vibrant colors, manga" '
            "and reflect this throughout all other fields.\n"
        ),
        "cont_note": (
            "Maintain the Japanese anime style: cel-shaded, vibrant saturated colors, expressive characters.\n"
        ),
        "dialog_field": "",
    },
    "watercolor": {
        "description": "Soft translucent watercolor brush strokes, bleeding ink edges, pastel tones, visible paper texture, impressionistic detail.",
        "init_note": (
            "The image MUST be in a soft watercolor painting style: delicate translucent brush strokes, "
            "bleeding ink edges, pastel and muted tones with visible paper texture, impressionistic detail. "
            'Set "aesthetics.style" to "watercolor painting, soft brush strokes, pastel tones, paper texture" '
            "and reflect this throughout all other fields.\n"
        ),
        "cont_note": (
            "Maintain the watercolor painting style: soft translucent brush strokes, pastel tones, paper texture.\n"
        ),
        "dialog_field": "",
    },
    "studio-ghibli": {
        "description": "Studio Ghibli hand-painted lush backgrounds, whimsical character design, soft natural lighting, warm nostalgic atmosphere.",
        "init_note": (
            "The image MUST be in a Studio Ghibli animation style: lush hand-painted backgrounds, "
            "whimsical character design, soft natural lighting, intricate environmental detail, "
            'painterly skies and foliage, warm nostalgic atmosphere. Set "aesthetics.style" to '
            '"Studio Ghibli animation, hand-painted, lush backgrounds, whimsical, nostalgic" '
            "and reflect this throughout all other fields.\n"
        ),
        "cont_note": (
            "Maintain the Studio Ghibli style: lush hand-painted backgrounds, whimsical characters, "
            "warm nostalgic atmosphere.\n"
        ),
        "dialog_field": "",
    },
    "oil-painting": {
        "description": "Classical oil painting — rich impasto texture, dramatic chiaroscuro, deep pigments, Rembrandt/Caravaggio Old Masters style.",
        "init_note": (
            "The image MUST be in a classical oil painting style: rich impasto texture, "
            "dramatic chiaroscuro lighting, deep saturated pigments, visible expressive brushwork, "
            'Old Masters inspired composition (Rembrandt/Caravaggio). Set "aesthetics.style" to '
            '"classical oil painting, impasto texture, chiaroscuro, Old Masters" '
            "and reflect this throughout all other fields.\n"
        ),
        "cont_note": (
            "Maintain the classical oil painting style: rich impasto texture, dramatic chiaroscuro, visible brushwork.\n"
        ),
        "dialog_field": "",
    },
    "retro-80s": {
        "description": "1980s synthwave/vaporwave — neon pinks, purples and cyans, chrome lettering, perspective grid lines, Miami Vice palette.",
        "init_note": (
            "The image MUST be in a retro 1980s aesthetic: neon pinks, purples and cyans, "
            "synthwave/vaporwave vibes, chrome lettering, perspective grid lines, lens flares, "
            'sunset gradients, Miami Vice color palette. Set "aesthetics.style" to '
            '"retro 1980s synthwave, neon colors, vaporwave, Miami Vice aesthetic" '
            "and reflect this throughout all other fields.\n"
        ),
        "cont_note": (
            "Maintain the retro 1980s synthwave style: neon colors, vaporwave vibes, chrome and grid aesthetics.\n"
        ),
        "dialog_field": "",
    },
    "retro-50s": {
        "description": "1950s Americana — warm Technicolor palette, atomic age optimism, diner culture, halftone print, vintage ad illustration.",
        "init_note": (
            "The image MUST be in a retro 1950s Americana aesthetic: warm muted Technicolor palette, "
            "diner culture, atomic age optimism, drive-ins, poodle skirts, tail-fin cars, "
            "halftone print textures, vintage advertising illustration style with clean graphic shapes. "
            'Set "aesthetics.style" to '
            '"retro 1950s Americana, Technicolor, atomic age, vintage advertising illustration" '
            "and reflect this throughout all other fields.\n"
        ),
        "cont_note": (
            "Maintain the retro 1950s Americana style: warm Technicolor palette, atomic age optimism, "
            "vintage advertising illustration with halftone textures.\n"
        ),
        "dialog_field": "",
    },
    "cyberpunk": {
        "description": "Neon-soaked dystopian megacity, holographic ads, chrome implants, deep shadows with neon highlights, Blade Runner aesthetic.",
        "init_note": (
            "The image MUST be in a cyberpunk aesthetic: neon-soaked rain-drenched megacity, "
            "holographic advertisements, chrome implants and biomechanical augmentations, "
            "dystopian high-tech low-life atmosphere, deep shadows with neon blue/green/pink highlights, "
            'dense urban sprawl. Set "aesthetics.style" to '
            '"cyberpunk, neon-lit dystopia, holographic, biomechanical, Blade Runner aesthetic" '
            "and reflect this throughout all other fields.\n"
        ),
        "cont_note": (
            "Maintain the cyberpunk style: neon-lit rain-soaked city, holographic elements, "
            "chrome and biomechanical details, dystopian atmosphere.\n"
        ),
        "dialog_field": "",
    },
    "fantasy": {
        "description": "High fantasy epic painting — sweeping grand landscapes, magical glowing elements, ornate armor, jewel tones with golden god-rays.",
        "init_note": (
            "The image MUST be in a high fantasy epic painting style: sweeping grand landscapes, "
            "magical glowing elements, ornate armor and arcane artifacts, dramatic god-rays and magical light, "
            "mythical creatures, rich jewel-toned colors with golden accents, "
            'reminiscent of classic fantasy book cover art. Set "aesthetics.style" to '
            '"high fantasy epic illustration, magical, grand landscapes, ornate, jewel tones, golden light" '
            "and reflect this throughout all other fields.\n"
        ),
        "cont_note": (
            "Maintain the high fantasy epic style: sweeping landscapes, magical glowing elements, "
            "ornate details, dramatic lighting with jewel tones.\n"
        ),
        "dialog_field": "",
    },
    "pixel-art": {
        "description": "Retro 8-bit/16-bit pixel art — visible square pixels, limited 16-32 color palette, hard edges, NES/SNES video game sprite aesthetic.",
        "init_note": (
            "The image MUST be in a retro pixel art style: visible square pixels, limited color palette "
            "of 16-32 colors, crisp hard edges with no anti-aliasing, isometric or side-scrolling game aesthetic, "
            "reminiscent of 8-bit and 16-bit era video games (NES/SNES/Sega). "
            'Set "aesthetics.style" to '
            '"retro pixel art, 16-bit, limited color palette, sharp pixels, video game sprite" '
            "and reflect this throughout all other fields.\n"
        ),
        "cont_note": (
            "Maintain the retro pixel art style: visible pixels, limited color palette, "
            "hard edges, 8-bit/16-bit video game aesthetic.\n"
        ),
        "dialog_field": "",
    },
    "impressionist": {
        "description": "French Impressionist painting — loose visible brushstrokes, dappled sunlight, soft blended colors, Monet/Renoir plein air style.",
        "init_note": (
            "The image MUST be in a French Impressionist painting style: loose visible brushstrokes, "
            "captured light and atmosphere over precise detail, dappled sunlight effects, "
            "soft blended colors, plein air outdoor scenes, Monet/Renoir/Pissarro inspired palette "
            "of lilac, soft green, golden yellow and sky blue. "
            'Set "aesthetics.style" to '
            '"French Impressionist painting, loose brushstrokes, dappled light, Monet style, plein air" '
            "and reflect this throughout all other fields.\n"
        ),
        "cont_note": (
            "Maintain the French Impressionist style: loose visible brushstrokes, dappled light, "
            "soft atmospheric colors, Monet/Renoir inspired palette.\n"
        ),
        "dialog_field": "",
    },
    "horror": {
        "description": "Cinematic psychological horror — desaturated palette, deep blacks, unsettling composition, grotesque details, James Wan / del Toro style.",
        "init_note": (
            "The image MUST be in a cinematic psychological horror style: desaturated palette with deep blacks, "
            "unsettling off-kilter composition, harsh directional shadows, grotesque distorted details, "
            "fog and darkness obscuring forms, dread-inducing atmosphere, "
            "reminiscent of James Wan and Guillermo del Toro visual style. "
            'Set "aesthetics.style" to '
            '"cinematic horror, desaturated, deep shadows, unsettling composition, psychological dread" '
            "and reflect this throughout all other fields.\n"
        ),
        "cont_note": (
            "Maintain the cinematic horror style: desaturated palette, deep shadows, unsettling composition, "
            "dread-inducing atmosphere.\n"
        ),
        "dialog_field": "",
    },
    "ukiyo-e": {
        "description": "Japanese ukiyo-e woodblock print — flat bold color areas, strong black outlines, Hokusai/Hiroshige composition, indigo and vermillion palette.",
        "init_note": (
            "The image MUST be in a traditional Japanese ukiyo-e woodblock print style: "
            "flat areas of bold color, strong black outlines, intricate pattern details, "
            "stylized waves and nature motifs, Hokusai/Hiroshige inspired composition, "
            "limited color palette with indigo blue, vermillion, black and cream. "
            'Set "aesthetics.style" to '
            '"Japanese ukiyo-e woodblock print, Hokusai style, bold outlines, flat colors, traditional" '
            "and reflect this throughout all other fields.\n"
        ),
        "cont_note": (
            "Maintain the ukiyo-e woodblock print style: flat bold colors, strong black outlines, "
            "Hokusai/Hiroshige inspired patterns and composition.\n"
        ),
        "dialog_field": "",
    },
    "claymation": {
        "description": "Claymation stop-motion — visible clay textures, fingerprint marks, wobbly organic forms, Aardman/Wallace & Gromit bright cheerful style.",
        "init_note": (
            "The image MUST look like a claymation stop-motion animation scene: handmade clay textures "
            "visible on all surfaces and characters, fingerprint marks and imperfections, "
            "slightly wobbly organic forms, bright cheerful colors, Aardman/Wallace and Gromit aesthetic, "
            "tactile three-dimensional clay quality with soft edges. "
            'Set "aesthetics.style" to '
            '"claymation stop-motion, clay texture, handmade, Aardman style, tactile, cheerful" '
            "and reflect this throughout all other fields.\n"
        ),
        "cont_note": (
            "Maintain the claymation stop-motion style: visible clay texture, handmade imperfections, "
            "bright colors, tactile organic forms.\n"
        ),
        "dialog_field": "",
    },
    "art-nouveau": {
        "description": "Art Nouveau — flowing organic lines, ornate botanical borders, elegant elongated figures, Alphonse Mucha flat decorative style.",
        "init_note": (
            "The image MUST be in an Art Nouveau style: flowing organic lines inspired by nature, "
            "ornate decorative borders with intertwined flora and fauna, elegant elongated figures, "
            "muted jewel tones with gold accents, Alphonse Mucha inspired flat decorative composition, "
            "intricate botanical motifs. "
            'Set "aesthetics.style" to '
            '"Art Nouveau, Alphonse Mucha style, flowing organic lines, ornate botanical, decorative" '
            "and reflect this throughout all other fields.\n"
        ),
        "cont_note": (
            "Maintain the Art Nouveau style: flowing organic lines, ornate botanical decorative borders, "
            "muted jewel tones, Mucha-inspired flat composition.\n"
        ),
        "dialog_field": "",
    },
    "documentary": {
        "description": "Cinematic documentary photography — candid natural light, desaturated realistic tones, film grain, photojournalism National Geographic style.",
        "init_note": (
            "The image MUST have a cinematic documentary photography style: candid unposed moments, "
            "natural available light only, slightly desaturated realistic color grading, "
            "handheld camera aesthetic with intentional grain, tight photojournalistic framing, "
            "raw authentic atmosphere reminiscent of National Geographic or Magnum Photos. "
            'Set "aesthetics.style" to '
            '"documentary photography, photojournalism, candid, natural light, film grain, National Geographic" '
            "and reflect this throughout all other fields.\n"
        ),
        "cont_note": (
            "Maintain the documentary photography style: candid natural light, desaturated realistic tones, "
            "film grain, photojournalistic framing.\n"
        ),
        "dialog_field": "",
    },
    "low-poly": {
        "description": "Low-poly 3D geometric art — flat-shaded triangular polygons, faceted crystal-like surfaces, bold color blocks, modern digital illustration.",
        "init_note": (
            "The image MUST be in a low-poly 3D geometric art style: scenes composed entirely of flat-shaded "
            "triangular polygons, faceted crystal-like surfaces, minimal vertex count giving angular geometric forms, "
            "clean bold color blocks with sharp polygon edges, modern digital illustration aesthetic. "
            'Set "aesthetics.style" to '
            '"low-poly 3D geometric, flat-shaded triangles, faceted crystal, angular forms, modern digital art" '
            "and reflect this throughout all other fields.\n"
        ),
        "cont_note": (
            "Maintain the low-poly geometric style: flat-shaded triangular polygons, faceted surfaces, "
            "angular forms with bold color blocks.\n"
        ),
        "dialog_field": "",
    },
    "retro-70s": {
        "description": "1970s retro aesthetic — warm amber and avocado tones, grainy film look, bell-bottom culture, vintage photo fading, analog warmth.",
        "init_note": (
            "The image MUST be in a retro 1970s aesthetic: warm amber, burnt orange, mustard yellow and avocado green tones, "
            "grainy analog film texture with visible grain and slight color fading, "
            "soft warm vignette edges, bell-bottom era fashion, macramé and earth-tone interiors, "
            "vintage Polaroid or Kodachrome color grading, natural sun-drenched warmth. "
            'Set "aesthetics.style" to '
            '"retro 1970s, warm amber tones, analog film grain, Kodachrome, vintage Polaroid, earth tones" '
            "and reflect this throughout all other fields.\n"
        ),
        "cont_note": (
            "Maintain the retro 1970s style: warm amber and earth tones, analog film grain, "
            "Kodachrome color grading, vintage Polaroid warmth.\n"
        ),
        "dialog_field": "",
    },
    "sci-fi": {
        "description": "Epic sci-fi concept art — vast alien environments, glowing technology, hard-surface spacecraft, dramatic cosmic lighting, Syd Mead / Mass Effect aesthetic.",
        "init_note": (
            "The image MUST be in an epic sci-fi concept art style: vast alien or space environments, "
            "glowing bioluminescent or technological light sources, hard-surface industrial spacecraft and structures, "
            "dramatic cosmic or planetary lighting, advanced futuristic technology with intricate detail, "
            "cinematic scale and grandeur inspired by Syd Mead, Mass Effect and Star Wars concept art. "
            'Set "aesthetics.style" to '
            '"sci-fi concept art, epic scale, futuristic technology, cosmic lighting, Syd Mead, Mass Effect" '
            "and reflect this throughout all other fields.\n"
        ),
        "cont_note": (
            "Maintain the sci-fi concept art style: vast environments, glowing technology, "
            "hard-surface structures, dramatic cosmic lighting and epic cinematic scale.\n"
        ),
        "dialog_field": "",
    },
    "sport": {
        "description": "Dynamic sports photography — freeze-frame peak action, motion blur, dramatic stadium lighting, high contrast, ESPN/Sports Illustrated editorial style.",
        "init_note": (
            "The image MUST be in a dynamic sports photography style: freeze-frame peak action moment, "
            "selective motion blur on extremities conveying speed, dramatic stadium or arena lighting, "
            "high contrast with rich saturated colors, tight athletic framing, "
            "sweat and physical intensity visible, ESPN or Sports Illustrated editorial quality, "
            "shallow depth of field with sharp subject against blurred crowd or environment. "
            'Set "aesthetics.style" to '
            '"dynamic sports photography, peak action, motion blur, stadium lighting, ESPN editorial, high contrast" '
            "and reflect this throughout all other fields.\n"
        ),
        "cont_note": (
            "Maintain the dynamic sports photography style: peak action freeze-frame, motion blur, "
            "dramatic stadium lighting, high contrast, ESPN editorial quality.\n"
        ),
        "dialog_field": "",
    },
}

# Constraints
EXTENSION_RESOLUTION = "720p"
RESOLUTIONS_REQUIRING_8S = {"1080p", "4k"}
MAX_POLL_SECONDS_VIDEO = 720   # 12 minutes
MAX_POLL_SECONDS_EXTEND = 360  # 6 minutes
POLL_INTERVAL = 10

# Pricing (USD) — as of March 2026
# Veo: per second of video generated
VEO_PRICE_PER_SEC = {"720p": 0.40, "1080p": 0.40, "4k": 0.60}
# Gemini Pro: per 1M tokens
TEXT_INPUT_PRICE_PER_M  = 2.00
TEXT_OUTPUT_PRICE_PER_M = 12.00
# Gemini Flash Image: per 1M tokens
IMAGE_INPUT_PRICE_PER_M  = 0.50
IMAGE_OUTPUT_PRICE_PER_M = 60.00  # image output tokens


class CostTracker:
    """Accumulates cost across all API calls in a session."""

    def __init__(self):
        self.items = []  # list of (label, cost)

    def add_video(self, seconds, resolution):
        price = VEO_PRICE_PER_SEC.get(resolution, 0.40)
        cost = seconds * price
        self.items.append((f"Video {seconds}s @ {resolution}", cost))

    def add_text(self, input_tokens, output_tokens, label="Extension prompts"):
        cost = (input_tokens / 1_000_000 * TEXT_INPUT_PRICE_PER_M +
                output_tokens / 1_000_000 * TEXT_OUTPUT_PRICE_PER_M)
        self.items.append((label, cost))

    def add_image(self, input_tokens, output_tokens, label="Reference image"):
        cost = (input_tokens / 1_000_000 * IMAGE_INPUT_PRICE_PER_M +
                output_tokens / 1_000_000 * IMAGE_OUTPUT_PRICE_PER_M)
        self.items.append((label, cost))

    def total(self):
        return sum(c for _, c in self.items)

    def print_summary(self):
        if not self.items:
            return
        print(f"\n{'─' * 45}")
        print("COST ESTIMATE")
        print(f"{'─' * 45}")
        for label, cost in self.items:
            print(f"  {label:<35} ${cost:.4f}")
        print(f"{'─' * 45}")
        print(f"  {'TOTAL':<35} ${self.total():.4f}")
        print(f"{'─' * 45}")
        print("  (Estimates based on published Google AI pricing)")


def generate_extension_prompts(client, original_prompt, num_extensions, cost_tracker=None):
    """Generate N extension prompts using gemini-3.1-pro-preview."""
    request = (
        f'Given this video prompt: "{original_prompt}"\n'
        f"Generate {num_extensions} continuation prompt(s) for extending the video.\n"
        "Each prompt describes what happens next in the scene (7-second segment).\n"
        "Return one prompt per line, no numbering.\n"
        "Preserve the face, skin tone, hairstyle, and overall identity of the main charecter.\n"
        "Do not alter the facial identity in the extensions.\n"
    )
    response = client.models.generate_content(model=TEXT_MODEL, contents=request)
    if cost_tracker and response.usage_metadata:
        cost_tracker.add_text(
            input_tokens=response.usage_metadata.prompt_token_count or 0,
            output_tokens=response.usage_metadata.candidates_token_count or 0,
        )
    prompts = [p.strip() for p in response.text.strip().splitlines() if p.strip()]
    # Pad with last prompt if fewer than requested
    while len(prompts) < num_extensions:
        prompts.append(prompts[-1] if prompts else original_prompt)
    return prompts[:num_extensions]


def generate_image_prompt_json(client, idea, cost_tracker=None, style=None):
    """Use TEXT_MODEL to generate a detailed structured JSON image prompt from a general idea."""
    style_def = STYLE_DEFINITIONS.get(style, {}) if style else {}
    style_note = style_def.get("init_note", "")
    dialog_field = style_def.get("dialog_field", "")
    request = (
        f'Given this general idea: "{idea}"\n'
        f"{style_note}"
        "Generate a detailed cinematic image prompt as a JSON object.\n"
        "The JSON must include these fields:\n"
        '  "id": a short snake_case identifier for the concept,\n'
        '  "prompt": an object with:\n'
        '    "subject": describe the main subject (brand/product/character/container if applicable),\n'
        '    "scene": {"description": ..., "environment": ...},\n'
        '    "agents": who/what is acting (if applicable),\n'
        '    "actions": list of action objects with "action", "object", "details",\n'
        '    "extra_elements": {"details": [list of small detail touches]},\n'
        '    "lighting": {"type", "style", "effects"},\n'
        '    "camera": {"type", "lens", "focus", "angle"},\n'
        '    "aesthetics": {"vibe", "quality", "style"},\n'
        f"{dialog_field}"
        '    "params": {"ar": "9:16" or "16:9", "stylize": 200, "quality": "ultra"}\n'
        "Return ONLY valid JSON, no markdown fences, no explanation."
    )
    response = client.models.generate_content(model=TEXT_MODEL, contents=request)
    if cost_tracker and response.usage_metadata:
        cost_tracker.add_text(
            input_tokens=response.usage_metadata.prompt_token_count or 0,
            output_tokens=response.usage_metadata.candidates_token_count or 0,
            label="Image prompt generation",
        )
    return response.text.strip()


def generate_video_prompt(client, idea, cost_tracker=None, style=None):
    """Use TEXT_MODEL to generate an enriched cinematic video prompt from a general idea."""
    style_def = STYLE_DEFINITIONS.get(style, {}) if style else {}
    style_note = style_def.get("init_note", "")

    request = (
        f'Given this general idea: "{idea}"\n'
        f"{style_note}"
        "Generate a detailed cinematic VIDEO prompt for a video generation model.\n"
        "Write a flowing, descriptive paragraph (not JSON, not bullet points) that covers:\n"
        "  - Subject & scene: who or what is in the scene and the environment\n"
        "  - Motion & action: what moves, how it moves, physical actions unfolding\n"
        "  - Camera work: movement (pan, tilt, dolly, zoom, crane, handheld, static), angle, lens\n"
        "  - Temporal flow: how the scene evolves from start to finish over a few seconds\n"
        "  - Lighting & atmosphere: quality and direction of light, mood, color palette\n"
        "  - Audio/sound design: ambient sounds, music tone, notable audio elements\n"
        "  - Visual quality: cinematic look, color grading, film format (e.g. 35mm, IMAX)\n"
        "Be vivid, specific, and cinematic. Do not include meta-commentary or instructions.\n"
        "Return ONLY the prompt text, nothing else."
    )
    response = client.models.generate_content(model=TEXT_MODEL, contents=request)
    if cost_tracker and response.usage_metadata:
        cost_tracker.add_text(
            input_tokens=response.usage_metadata.prompt_token_count or 0,
            output_tokens=response.usage_metadata.candidates_token_count or 0,
            label="Video prompt generation",
        )
    return response.text.strip()


def generate_continuation_prompt_json(client, previous_prompt_json, cost_tracker=None, style=None):
    """Use TEXT_MODEL to generate the next storyboard frame prompt, continuing from the previous JSON prompt."""
    style_def = STYLE_DEFINITIONS.get(style, {}) if style else {}
    style_note = style_def.get("cont_note", "")
    request = (
        "You are building a visual storyboard. Here is the previous frame's image prompt in JSON format:\n"
        f"{previous_prompt_json}\n\n"
        "Generate the NEXT frame's image prompt as a JSON object.\n"
        "Advance the story naturally: progress the action, move the camera, or evolve the scene.\n"
        f"{style_note}"
        "Keep the same subject, style, lighting aesthetic, and overall visual identity.\n"
        "Use the exact same JSON structure as the input.\n"
        "Return ONLY valid JSON, no markdown fences, no explanation."
    )
    response = client.models.generate_content(model=TEXT_MODEL, contents=request)
    if cost_tracker and response.usage_metadata:
        cost_tracker.add_text(
            input_tokens=response.usage_metadata.prompt_token_count or 0,
            output_tokens=response.usage_metadata.candidates_token_count or 0,
            label="Storyboard continuation prompt",
        )
    return response.text.strip()


def extract_last_frame(video_path, output_image_path):
    """Extract the last frame of a video using OpenCV and save it as an image."""
    print(f"   Extracting last frame from {video_path}...")
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video file: {video_path}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, total_frames - 1))

    ret, frame = cap.read()
    if ret:
        cv2.imwrite(str(output_image_path), frame)
        print(f"   Last frame saved to {output_image_path}")
    else:
        raise RuntimeError("Failed to read the last frame.")
    cap.release()
    return output_image_path


def generate_image_from_reference(client, prompt, image_path, output_dir, cost_tracker=None):
    """Use gemini-3.1-flash-image-preview to create an image from reference + prompt."""
    mime_type = "image/png" if str(image_path).lower().endswith(".png") else "image/jpeg"
    print(f"   Uploading reference image to Files API: {image_path}")
    uploaded = client.files.upload(
        file=image_path,
        config=types.UploadFileConfig(mime_type=mime_type, display_name=Path(image_path).name),
    )
    print(f"   Uploaded: {uploaded.name}  URI: {uploaded.uri}")

    response = client.models.generate_content(
        model=IMAGE_MODEL,
        contents=[
            types.Part(
                text=(
                    f"Create an image based on this description: {prompt}. "
                    "The provided photo is of a private individual (not a public figure or celebrity). "
                    "This image is being used with full consent for personal creative purposes. "
                    "Use the provided photo as the character reference. Preserve the face, skin tone, hairstyle, and overall identity. Do not alter the facial identity. "
                    "Use the provided photo as the exact visual reference. "
                    "The subject must closely match the face shape, eye shape, nose, lips, and overall facial structure from the reference. "
                    "Do not create a new person — replicate the look of the person in the uploaded image as faithfully as possible."
                )
            ),
            types.Part(file_data=types.FileData(file_uri=uploaded.uri, mime_type=mime_type)),
        ],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
        ),
    )

    if cost_tracker and response.usage_metadata:
        cost_tracker.add_image(
            input_tokens=response.usage_metadata.prompt_token_count or 0,
            output_tokens=response.usage_metadata.candidates_token_count or 0,
        )

    candidates = response.candidates or []
    if not candidates:
        finish = getattr(response, "prompt_feedback", None)
        raise RuntimeError(f"Image generation returned no candidates (possibly blocked). Feedback: {finish}")

    content = candidates[0].content
    parts = content.parts if content else []
    if not parts:
        finish_reason = getattr(candidates[0], "finish_reason", "unknown")
        raise RuntimeError(f"Image generation returned no parts (finish_reason={finish_reason})")

    for part in parts:
        if part.inline_data:
            ref_image_path = output_dir / "reference_image.png"
            with open(ref_image_path, "wb") as f:
                f.write(part.inline_data.data)
            return ref_image_path

    raise RuntimeError("Image generation produced no image output")


def generate_image_from_text(client, json_prompt, output_dir, filename="image.png", cost_tracker=None):
    """Use IMAGE_MODEL to generate an image from a text/JSON prompt with no reference image."""
    response = client.models.generate_content(
        model=IMAGE_MODEL,
        contents=[types.Part(text=json_prompt)],
        config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
    )
    if cost_tracker and response.usage_metadata:
        cost_tracker.add_image(
            input_tokens=response.usage_metadata.prompt_token_count or 0,
            output_tokens=response.usage_metadata.candidates_token_count or 0,
            label=f"Image generation ({filename})",
        )
    parts = response.candidates[0].content.parts or []
    for part in parts:
        if part.inline_data:
            image_path = output_dir / filename
            with open(image_path, "wb") as f:
                f.write(part.inline_data.data)
            return image_path
    raise RuntimeError("Image generation produced no image output")


def generate_image_variation(client, json_prompt, reference_image_path, output_dir, filename, cost_tracker=None):
    """Use IMAGE_MODEL to generate an image variation using a reference image and JSON prompt."""
    with open(reference_image_path, "rb") as f:
        image_bytes = f.read()
    response = client.models.generate_content(
        model=IMAGE_MODEL,
        contents=[
            types.Part(text=json_prompt),
            types.Part(inline_data=types.Blob(data=image_bytes, mime_type="image/png")),
        ],
        config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
    )
    if cost_tracker and response.usage_metadata:
        cost_tracker.add_image(
            input_tokens=response.usage_metadata.prompt_token_count or 0,
            output_tokens=response.usage_metadata.candidates_token_count or 0,
            label=f"Image variation ({filename})",
        )
    parts = response.candidates[0].content.parts or []
    for part in parts:
        if part.inline_data:
            image_path = output_dir / filename
            with open(image_path, "wb") as f:
                f.write(part.inline_data.data)
            return image_path
    raise RuntimeError("Image generation produced no image output")


def render_images_as_html(image_paths: list, output_dir: Path, title: str = "Generated Images") -> Path:
    """Embed images as base64 data URIs in a self-contained HTML file."""
    items = []
    for img_path in image_paths:
        data = base64.b64encode(Path(img_path).read_bytes()).decode()
        label = Path(img_path).name
        items.append(
            f'<figure>'
            f'<img src="data:image/png;base64,{data}" alt="{label}">'
            f'<figcaption>{label}</figcaption>'
            f'</figure>'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  body {{
    margin: 0;
    background: #111;
    color: #eee;
    font-family: sans-serif;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 2rem;
    gap: 2rem;
  }}
  h1 {{ font-size: 1.4rem; letter-spacing: .05em; color: #aaa; margin: 0; }}
  figure {{
    margin: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: .5rem;
  }}
  img {{
    max-width: min(100%, 960px);
    border-radius: 8px;
    box-shadow: 0 4px 24px rgba(0,0,0,.6);
  }}
  figcaption {{ font-size: .75rem; color: #666; }}
</style>
</head>
<body>
<h1>{title}</h1>
{''.join(items)}
</body>
</html>"""

    out = output_dir / "images.html"
    out.write_text(html, encoding="utf-8")
    return out


def generate_comics_dialog(client, prompt_jsons, cost_tracker=None):
    """Use TEXT_MODEL to generate per-panel dialog or captions for a comics page."""
    panels_info = "\n\n".join(f"Panel {i + 1}:\n{pj}" for i, pj in enumerate(prompt_jsons))
    request = (
        f"You are a professional comics writer. Here are {len(prompt_jsons)} storyboard frames as JSON prompts:\n\n"
        f"{panels_info}\n\n"
        "Write authentic comics-style dialogue or captions for each panel.\n"
        "\n"
        "COMICS DIALOGUE RULES (follow these strictly):\n"
        "  1. CONCISENESS: Every word must earn its place. Max 8 words per line, max 2 lines.\n"
        "     Comics readers skim — cut anything the image already shows.\n"
        "  2. FRAGMENTED SPEECH: Real people don't speak in full sentences.\n"
        "     Use contractions, sentence fragments, one-word reactions.\n"
        "  3. ELLIPSIS (...): For hesitation, trailing thoughts, or suspense.\n"
        "     Example: 'WAIT... THAT CAN'T BE...'\n"
        "  4. EM-DASH (--): For interrupted or cut-off speech.\n"
        "     Example: 'BUT I NEVER MEANT TO--'\n"
        "  5. VOICE: Give each character a distinct speech pattern.\n"
        "     Gruff characters use short grunts. Nervous ones use ...ellipses.\n"
        "  6. EMOTIONAL PUNCTUATION: Use ! for excitement/anger, ? for confusion.\n"
        "     SHOUT bubbles use !! or !!! and ALL CAPS with strong punchy words.\n"
        "  7. THOUGHT BUBBLES: For inner monologue — use bubble_type 'thought'.\n"
        "     These are cloud-shaped. Use italicised tone: hesitant, private.\n"
        "  8. CAPTION BOXES: For narrator voice, time/place, or scene transitions.\n"
        "     Examples: 'THREE HOURS EARLIER...' / 'MEANWHILE, ACROSS TOWN...' / short mood-setting line.\n"
        "  9. ACTION PANELS: If no characters are speaking, use a caption OR leave dialog empty.\n"
        "     Never force dialog into a silent action beat.\n"
        " 10. READING FLOW: Panels must read as a connected story. Each panel's text\n"
        "     should logically follow from the previous panel.\n"
        "\n"
        "bubble_type options:\n"
        "  'speech'  — standard oval balloon, normal conversation\n"
        "  'shout'   — jagged starburst, excited/angry (use ! or !!)\n"
        "  'whisper' — dashed oval, quiet/secretive\n"
        "  'thought' — cloud-shaped balloon, internal monologue\n"
        "\n"
        "Return a JSON array — one object per panel — in this exact format:\n"
        '  characters: {"panel":1,"has_characters":true,"speaker":"Name","dialog":"TEXT","bubble_type":"speech"}\n'
        '  narration:  {"panel":1,"has_characters":false,"caption":"TEXT"}\n'
        "ALL TEXT must be ALL CAPS. Return ONLY a valid JSON array, no markdown, no explanation."
    )
    response = client.models.generate_content(model=TEXT_MODEL, contents=request)
    if cost_tracker and response.usage_metadata:
        cost_tracker.add_text(
            input_tokens=response.usage_metadata.prompt_token_count or 0,
            output_tokens=response.usage_metadata.candidates_token_count or 0,
            label="Comics dialog generation",
        )
    import json
    raw = response.text.strip()
    # Strip markdown fences if the model added them anyway
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return [{"panel": i + 1, "has_characters": False, "caption": ""} for i in range(len(prompt_jsons))]


# ── Comics layout engine ──────────────────────────────────────────────────────

# Layouts keyed by panel count. Each tier is a list of relative column widths.
# tier_h lists relative heights for each tier row.
# Layouts use varied column weights so panels are NOT equal-width.
# [2, 1] means the left panel is twice as wide as the right — creates visual hierarchy.
# Alternating wide/narrow across rows creates an X-pattern diagonal flow.
_COMIC_LAYOUTS = {
    1: {"tiers": [[1]],                        "tier_h": [1]},
    2: {"tiers": [[1], [1]],                   "tier_h": [1.6, 1]},      # big top + smaller bottom
    3: {"tiers": [[1], [1, 1]],                "tier_h": [1.7, 1]},      # wide establishing + 2 panels
    4: {"tiers": [[2, 1], [1, 2]],             "tier_h": [1.1, 1]},      # X-pattern: left-heavy / right-heavy
    5: {"tiers": [[2, 1], [1, 1, 1]],          "tier_h": [1.5, 1]},      # big opener + 3 fast panels
    6: {"tiers": [[1, 2], [2, 1], [1, 1]],     "tier_h": [1.1, 1.1, 0.85]},  # cinematic alternating focus
}
_PANELS_PER_PAGE = 6


def optimal_panels_per_page(page_w=1500, page_h=2325, margin=18, gutter=14, img_aspect=1.0):
    """
    Return the number of panels per page that maximises page coverage for the given
    image aspect ratio (width/height).  The function tries every (cols, rows) grid
    and picks the combination whose panels occupy the largest fraction of the
    available page area, subject to a minimum panel size of 200 px per side.
    """
    import math
    avail_w = page_w - 2 * margin
    avail_h = page_h - 2 * margin
    MIN_PX = 200
    best_n, best_cov = 1, 0.0
    for n in range(1, 10):
        for cols in range(1, n + 1):
            rows = math.ceil(n / cols)
            # Scale to fill width first
            pw = (avail_w - (cols - 1) * gutter) / cols
            ph = pw / img_aspect
            total_h = rows * ph + (rows - 1) * gutter
            if total_h > avail_h:
                # Clamp to fit height
                ph = (avail_h - (rows - 1) * gutter) / rows
                pw = ph * img_aspect
            if pw < MIN_PX or ph < MIN_PX:
                continue
            cov = (n * pw * ph) / (avail_w * avail_h)
            if cov > best_cov:
                best_cov, best_n = cov, n
    return best_n


def _comic_font(size):
    """Load a bold system font, falling back gracefully."""
    from PIL import ImageFont
    candidates = [
        ("/System/Library/Fonts/Helvetica.ttc", 1),                          # macOS bold
        ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 0),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 0),
        ("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 0),
        ("/System/Library/Fonts/Helvetica.ttc", 0),                          # regular fallback
    ]
    for path, idx in candidates:
        try:
            return ImageFont.truetype(path, size, index=idx)
        except Exception:
            pass
    return ImageFont.load_default()


def _wrap_text(draw, text, font, max_width):
    """Word-wrap text to max_width. Returns (lines, widths, heights)."""
    words = text.split()
    lines, widths, heights = [], [], []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        bb = draw.textbbox((0, 0), test, font=font)
        if bb[2] - bb[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    for line in lines:
        bb = draw.textbbox((0, 0), line, font=font)
        widths.append(bb[2] - bb[0])
        heights.append(bb[3] - bb[1])
    return lines, widths, heights


def _compute_panel_rects(n, page_w, page_h, margin, gutter):
    """Return list of (x0, y0, x1, y1) panel rects for n panels on one page."""
    layout = _COMIC_LAYOUTS.get(n, _COMIC_LAYOUTS[6])
    tiers = layout["tiers"]
    tier_h_weights = layout["tier_h"]
    total_th = sum(tier_h_weights)
    avail_h = page_h - 2 * margin - (len(tiers) - 1) * gutter
    avail_w = page_w - 2 * margin
    rects = []
    y = margin
    for cols, th in zip(tiers, tier_h_weights):
        tier_h = int(avail_h * th / total_th)
        total_cw = sum(cols)
        col_avail_w = avail_w - (len(cols) - 1) * gutter
        x = margin
        for cw in cols:
            pw = int(col_avail_w * cw / total_cw)
            rects.append((x, y, x + pw, y + tier_h))
            x += pw + gutter
        y += tier_h + gutter
    return rects


def _draw_caption_box(draw, panel_rect, text, font):
    """Yellow narration caption box at the top of a panel (classic comics style)."""
    YELLOW = (255, 235, 80)
    PAD_H, PAD_V = 12, 7
    px, py, px2, _ = panel_rect
    max_w = (px2 - px) - 20
    lines, widths, heights = _wrap_text(draw, text.upper(), font, max_w - PAD_H * 2)
    if not lines:
        return
    line_h = max(heights)
    box_h = len(lines) * line_h + (len(lines) - 1) * 4 + PAD_V * 2
    bx, by = px + 10, py + 10
    draw.rectangle([bx, by, bx + max_w, by + box_h], fill=YELLOW, outline=(0, 0, 0), width=2)
    y_t = by + PAD_V
    for line, lw, lh in zip(lines, widths, heights):
        draw.text((bx + PAD_H, y_t), line, fill=(0, 0, 0), font=font)
        y_t += lh + 4


def _draw_speech_bubble(draw, panel_rect, text, font, bubble_type="speech"):
    """Draw a speech bubble overlaying the panel image, tail pointing downward to the speaker."""
    import math
    px, py, px2, py2 = panel_rect
    pw = px2 - px
    ph = py2 - py
    PAD_H, PAD_V = 16, 11
    LINE_GAP = 4
    WHITE = (255, 255, 255)
    BLACK = (0, 0, 0)

    max_bubble_w = int(pw * 0.72)
    lines, widths, heights = _wrap_text(draw, text.upper(), font, max_bubble_w - PAD_H * 2)
    if not lines:
        return

    text_w = max(widths)
    text_h = sum(heights) + LINE_GAP * (len(lines) - 1)
    bw = text_w + PAD_H * 2
    bh = text_h + PAD_V * 2
    # Position bubble 12% from top, horizontally centered
    bx = px + (pw - bw) // 2
    by = py + int(ph * 0.12)
    radius = min(bh // 2, bw // 4, 30)

    if bubble_type == "shout":
        # Jagged starburst balloon — draw centered on the bubble's intended location
        cx = bx + bw // 2
        cy = by + bh // 2
        outer_r = max(bw, bh) // 2 + 18
        inner_r = max(bw, bh) // 2 - 6
        n_spikes = 16
        pts = []
        for i in range(n_spikes * 2):
            angle = 2 * math.pi * i / (n_spikes * 2) - math.pi / 2
            r = outer_r if i % 2 == 0 else inner_r
            pts.append((int(cx + r * math.cos(angle)), int(cy + r * math.sin(angle))))
        draw.polygon(pts, fill=WHITE, outline=BLACK)
        # text draws from original bx/by which are already centered on cx/cy
    elif bubble_type == "thought":
        # Cloud-shaped thought balloon: large oval + small circles trailing down to speaker
        cx = bx + bw // 2
        cy = by + bh // 2
        rx = bw // 2 + 10
        ry = bh // 2 + 8
        # Draw main cloud body as a series of overlapping circles along the ellipse perimeter
        n_bumps = 10
        for i in range(n_bumps):
            angle = 2 * math.pi * i / n_bumps
            bumpx = int(cx + rx * 0.85 * math.cos(angle))
            bumpy = int(cy + ry * 0.85 * math.sin(angle))
            bump_r = int(min(rx, ry) * 0.38)
            draw.ellipse([bumpx - bump_r, bumpy - bump_r, bumpx + bump_r, bumpy + bump_r],
                         fill=WHITE, outline=BLACK)
        # Fill centre to hide gaps
        draw.ellipse([cx - rx + 8, cy - ry + 8, cx + rx - 8, cy + ry - 8], fill=WHITE, outline=WHITE)
        # Thought trail — three small circles leading down
        TRAIL_W = 12
        trail_cx = bx + bw // 2
        trail_base_y = by + bh
        for j, (tr, ty) in enumerate([(TRAIL_W, trail_base_y + 10),
                                       (TRAIL_W - 4, trail_base_y + 24),
                                       (TRAIL_W - 7, trail_base_y + 36)]):
            draw.ellipse([trail_cx - tr, ty - tr, trail_cx + tr, ty + tr], fill=WHITE, outline=BLACK)
    else:
        # Draw tail FIRST (bubble body drawn on top will cover tail base cleanly)
        TAIL_W = 14
        TAIL_H = 30
        tail_cx = bx + bw // 2
        tail_base_y = by + bh
        tail_tip_y = min(tail_base_y + TAIL_H, py + int(ph * 0.78))
        # Slightly offset tip for a natural angle
        tail_tip_x = tail_cx + int(pw * 0.05)
        tail_pts = [(tail_cx - TAIL_W, tail_base_y), (tail_cx + TAIL_W, tail_base_y), (tail_tip_x, tail_tip_y)]
        draw.polygon(tail_pts, fill=WHITE, outline=BLACK)

        border_w = 2 if bubble_type == "whisper" else 3
        draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=radius,
                               fill=WHITE, outline=BLACK, width=border_w)
        if bubble_type == "whisper":
            step = 10
            for dx in range(0, bw, step * 2):
                draw.rectangle([bx + dx, by, bx + min(dx + step, bw), by + 3], fill=(160, 160, 160))
                draw.rectangle([bx + dx, by + bh - 3, bx + min(dx + step, bw), by + bh], fill=(160, 160, 160))

    # Text centered within the bubble
    y_t = by + PAD_V
    for line, lw, lh in zip(lines, widths, heights):
        x_t = bx + PAD_H + (text_w - lw) // 2
        draw.text((x_t, y_t), line, fill=BLACK, font=font)
        y_t += lh + LINE_GAP


def _draw_speech_bubble_corner(draw, panel_rect, text, font, bubble_type="speech"):
    """Draw a small speech bubble anchored to the bottom-left corner of a panel.

    Keeps the bubble away from the centre of the image so it is unlikely to
    cover the main characters.  The bubble is intentionally compact (max 45 %
    of the panel width) and placed in the lower-left quadrant.
    """
    import math
    px, py, px2, py2 = panel_rect
    pw = px2 - px
    ph = py2 - py
    PAD_H, PAD_V = 12, 8
    LINE_GAP = 3
    WHITE = (255, 255, 255)
    BLACK = (0, 0, 0)

    max_bubble_w = int(pw * 0.45)
    lines, widths, heights = _wrap_text(draw, text.upper(), font, max_bubble_w - PAD_H * 2)
    if not lines:
        return

    text_w = max(widths)
    text_h = sum(heights) + LINE_GAP * (len(lines) - 1)
    bw = text_w + PAD_H * 2
    bh = text_h + PAD_V * 2

    # Anchor: bottom-left, with a small inset so it sits inside the panel
    INSET = 10
    bx = px + INSET
    by = py2 - bh - INSET - 28  # leave room for tail below

    radius = min(bh // 2, bw // 4, 20)

    if bubble_type == "shout":
        cx = bx + bw // 2
        cy = by + bh // 2
        outer_r = max(bw, bh) // 2 + 14
        inner_r = max(bw, bh) // 2 - 4
        n_spikes = 14
        pts = []
        for i in range(n_spikes * 2):
            angle = 2 * math.pi * i / (n_spikes * 2) - math.pi / 2
            r = outer_r if i % 2 == 0 else inner_r
            pts.append((int(cx + r * math.cos(angle)), int(cy + r * math.sin(angle))))
        draw.polygon(pts, fill=WHITE, outline=BLACK)
    else:
        # Small tail pointing downward-left toward the speaker area
        TAIL_W = 10
        TAIL_H = 22
        tail_cx = bx + bw // 3
        tail_base_y = by + bh
        tail_tip_x = tail_cx - 6
        tail_tip_y = min(tail_base_y + TAIL_H, py2 - INSET)
        tail_pts = [(tail_cx - TAIL_W, tail_base_y), (tail_cx + TAIL_W, tail_base_y), (tail_tip_x, tail_tip_y)]
        draw.polygon(tail_pts, fill=WHITE, outline=BLACK)

        border_w = 2 if bubble_type == "whisper" else 2
        draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=radius,
                               fill=WHITE, outline=BLACK, width=border_w)

    # Text
    y_t = by + PAD_V
    for line, lw, lh in zip(lines, widths, heights):
        x_t = bx + PAD_H + (text_w - lw) // 2
        draw.text((x_t, y_t), line, fill=BLACK, font=font)
        y_t += lh + LINE_GAP


def compose_comics_pages(image_paths, dialog_data, output_dir, style=None):
    """Compose storyboard images into professional-layout comics page(s).

    If *style* is ``"comics"`` the generated panel art already contains
    speech-bubbles baked in by the image model, so no overlay is added.
    For every other style small corner-positioned bubbles are overlaid so
    that they don't obscure the main characters.
    """
    from PIL import Image, ImageDraw

    # Standard US comic page portrait ratio ~1:1.55
    PAGE_W, PAGE_H = 1500, 2325
    # Black page background — gutters show as black gaps (print comics standard)
    PAGE_BG = (10, 10, 10)
    MARGIN = 18          # thin outer margin so panels nearly fill the page
    GUTTER = 14          # black gap between panels

    font_dialog = _comic_font(26)
    font_caption = _comic_font(22)

    pages_saved = []
    chunks = [image_paths[i:i + _PANELS_PER_PAGE] for i in range(0, len(image_paths), _PANELS_PER_PAGE)]

    for page_num, chunk in enumerate(chunks, start=1):
        page = Image.new("RGB", (PAGE_W, PAGE_H), PAGE_BG)
        draw = ImageDraw.Draw(page)

        rects = _compute_panel_rects(len(chunk), PAGE_W, PAGE_H, MARGIN, GUTTER)

        for idx, img_path in enumerate(chunk):
            panel_idx = (page_num - 1) * _PANELS_PER_PAGE + idx
            px, py, px2, py2 = rects[idx]
            pw, ph = px2 - px, py2 - py

            # Crop-to-fill: scale image so it covers the panel completely, then
            # center-crop.  Proportions are always preserved — only the outermost
            # edge pixels may be trimmed (typically < 5 %).  No black bars.
            img = Image.open(img_path)
            iw, ih = img.size
            scale = max(pw / iw, ph / ih)          # fill, not fit
            nw, nh = int(iw * scale), int(ih * scale)
            img = img.resize((nw, nh), Image.LANCZOS)
            cx = (nw - pw) // 2
            cy = (nh - ph) // 2
            img = img.crop((cx, cy, cx + pw, cy + ph))
            page.paste(img, (px, py))

            # Overlay dialog or caption ON TOP of the image.
            # Comics style: the AI already rendered speech bubbles inside the
            # panel art — adding a second layer would double them up, so skip.
            # All other styles: draw a small corner bubble that avoids the
            # main characters (placed bottom-left, max 45 % of panel width).
            panel_data = dialog_data[panel_idx] if panel_idx < len(dialog_data) else {}
            if style != "comics":
                if panel_data.get("has_characters") and panel_data.get("dialog"):
                    text = panel_data["dialog"]
                    btype = panel_data.get("bubble_type", "speech")
                    _draw_speech_bubble_corner(draw, (px, py, px2, py2), text, font_dialog, btype)
                elif panel_data.get("caption"):
                    _draw_caption_box(draw, (px, py, px2, py2), panel_data["caption"], font_caption)

        out_path = output_dir / f"comics_page_{page_num}.png"
        page.save(out_path)
        pages_saved.append(out_path)
        print(f"   Comics page {page_num} saved to: {out_path}")

    return pages_saved


def poll_operation(client, operation, max_wait):
    """Poll an operation until done and return the generated video."""
    progress_messages = [
        (15,  "Analyzing prompt and setting up scene..."),
        (30,  "Rendering initial frames..."),
        (60,  "Processing video segments..."),
        (90,  "Adding details and effects..."),
        (120, "Generating synchronized audio..."),
        (180, "Finalizing video composition..."),
        (240, "Almost there, finishing up..."),
    ]
    shown_messages = set()
    start_time = time.time()
    poll_count = 0

    while not getattr(operation, "done", False):
        elapsed = int(time.time() - start_time)
        poll_count += 1

        for threshold, message in progress_messages:
            if elapsed >= threshold and threshold not in shown_messages:
                print(f"   {message}")
                shown_messages.add(threshold)

        print(f"   In progress... {elapsed}s elapsed (poll #{poll_count})")

        if elapsed > max_wait:
            raise TimeoutError(f"Operation timed out after {max_wait}s")

        time.sleep(POLL_INTERVAL)
        operation = client.operations.get(operation)

    elapsed = int(time.time() - start_time)
    minutes, seconds = divmod(elapsed, 60)
    time_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"
    print(f"\n   Completed in {time_str} (polls: {poll_count})")

    # Check for errors in the completed operation
    if getattr(operation, "error", None):
        print(f"\n[DEBUG] Operation error details:")
        print(f"   error        : {operation.error}")
        print(f"   error type   : {type(operation.error)}")
        try:
            print(f"   error dict   : {dict(operation.error)}")
        except Exception:
            pass
        print(f"   operation.name : {getattr(operation, 'name', 'N/A')}")
        print(f"   operation.done : {getattr(operation, 'done', 'N/A')}")
        print(f"   operation.metadata : {getattr(operation, 'metadata', 'N/A')}")
        print(f"   operation (full) : {operation}")
        raise RuntimeError(f"Operation failed: {operation.error}")

    response = getattr(operation, "response", None)
    videos = getattr(response, "generated_videos", None) if response else None

    if not videos:
        # Try to extract a human-readable rejection reason
        reason = None
        if response:
            reason = getattr(response, "error", None) or getattr(response, "message", None)
        if not reason and operation:
            reason = getattr(operation, "error", None) or getattr(operation, "message", None)
        if not reason:
            reason = "No videos were generated (possible content policy rejection)"
        raise RuntimeError(str(reason))

    return videos[0].video


def generate_video(client, prompt, resolution, aspect_ratio, reference_image_path=None,
                   cost_tracker=None):
    """Generate a video using Veo 3.1 and poll until complete."""
    duration = 8 if resolution in RESOLUTIONS_REQUIRING_8S else 4

    print(f"\nGenerating video with {VEO_MODEL}...")
    print(f"   Duration: {duration}s | Resolution: {resolution} | Aspect Ratio: {aspect_ratio}")

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

    generate_kwargs = {"model": VEO_MODEL, "prompt": video_prompt, "config": config}

    print(f"\n[DEBUG] generate_videos kwargs:")
    print(f"   model        : {VEO_MODEL}")
    print(f"   duration     : {duration}s")
    print(f"   resolution   : {resolution}")
    print(f"   aspect_ratio : {aspect_ratio}")
    print(f"   prompt (first 200 chars): {video_prompt[:200]!r}")

    if reference_image_path:
        mime_type = "image/png" if str(reference_image_path).lower().endswith(".png") else "image/jpeg"
        print(f"   Uploading reference image to Files API: {reference_image_path}")
        uploaded = client.files.upload(
            file=reference_image_path,
            config=types.UploadFileConfig(mime_type=mime_type, display_name=Path(reference_image_path).name),
        )
        print(f"   Uploaded: {uploaded.name}  URI: {uploaded.uri}")
        generate_kwargs["image"] = types.Image(gcs_uri=uploaded.uri)

    operation = client.models.generate_videos(**generate_kwargs)

    operation_name = getattr(operation, "name", str(operation))
    print(f"   Operation started: {operation_name}")

    video_file = poll_operation(client, operation, max_wait=MAX_POLL_SECONDS_VIDEO)

    if cost_tracker:
        cost_tracker.add_video(duration, resolution)

    print("   Downloading video...")
    client.files.download(file=video_file)

    return video_file


def extend_video_chain(client, initial_video, extension_prompts, output_dir, resolution, aspect_ratio, extend_method="image", cost_tracker=None):
    """Extend a video N times.

    If extend_method == "video", uses Veo's native video extension (forces 720p).
    If extend_method == "image", extracts the last frame and generates a new video from it.
    """
    current_video = initial_video
    num_extensions = len(extension_prompts)

    print(f"\nExtending video {num_extensions} time(s) using {extend_method} method...")

    # Save the initial video first
    initial_video_path = output_dir / "video_part_0.mp4"
    print(f"   Saving initial video part to {initial_video_path}...")
    current_video.save(str(initial_video_path))
    prev_video_path = initial_video_path

    for i, ext_prompt in enumerate(extension_prompts):
        print(f"\nExtension {i + 1}/{num_extensions}:")
        print(f"   Prompt: {ext_prompt}")

        if extend_method == "image":
            # Extract last frame
            ref_frame_path = output_dir / f"reference_frame_{i + 1}.png"
            extract_last_frame(prev_video_path, ref_frame_path)

            duration = 8 if resolution in RESOLUTIONS_REQUIRING_8S else 4
            print(f"   Resolution: {resolution} | Duration: {duration}s")

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
            # Native video extension
            print(f"   Resolution: {EXTENSION_RESOLUTION} (required for native video extensions)")
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

        operation_name = getattr(operation, "name", str(operation))
        print(f"   Extension operation started: {operation_name}")

        current_video = poll_operation(client, operation, max_wait=MAX_POLL_SECONDS_EXTEND)

        if cost_tracker:
            cost_tracker.add_video(expected_cost_seconds, resolution if extend_method == "image" else EXTENSION_RESOLUTION)

        # Download the newly generated video bytes into current_video
        print("   Downloading intermediate video...")
        client.files.download(file=current_video)

        # Save the new part immediately
        prev_video_path = output_dir / f"video_part_{i + 1}.mp4"
        print(f"   Saving video part to {prev_video_path}...")
        current_video.save(str(prev_video_path))

        # If native video extension is used, we need to pass just the URI reference for the next loop
        if extend_method == "video" and i < num_extensions - 1:
            current_video = types.Video(uri=current_video.uri)

    print(f"\nAll {num_extensions} extension(s) completed!")
    return current_video


def cmd_list(client, args):
    """List all files stored in the Google Files API."""
    files = list(client.files.list())
    if not files:
        print("No files found in your account.")
        return

    print(f"\n{'=' * 70}")
    print(f"{'NAME':<30} {'TYPE':<12} {'SIZE':>10}  {'EXPIRES':<20}  URI")
    print(f"{'=' * 70}")
    for f in files:
        name = f.name or ""
        mime = (f.mime_type or "")[:11]
        size = f"{f.size_bytes:,}" if getattr(f, "size_bytes", None) else "—"
        expiry = ""
        if getattr(f, "expiration_time", None):
            expiry = f.expiration_time.strftime("%Y-%m-%d %H:%M")
        uri = f.uri or ""
        print(f"{name:<30} {mime:<12} {size:>10}  {expiry:<20}  {uri}")

    print(f"\n{len(files)} file(s) total. Files expire 48h after creation.")
    print(f"\nTo download: python veo.py download <name>  (e.g. files/abc123)")


def cmd_download(client, args):
    """Download a file from the Google Files API by name."""
    file_obj = client.files.get(name=args.name)

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        # Derive a filename from the file name (last segment) + mime type
        slug = args.name.replace("/", "_")
        ext = ""
        mime = getattr(file_obj, "mime_type", "") or ""
        if "video" in mime:
            ext = ".mp4"
        elif "image" in mime:
            ext = ".png"
        output_path = Path(slug + ext)

    print(f"\nDownloading {args.name}...")
    print(f"   MIME type : {getattr(file_obj, 'mime_type', 'unknown')}")
    print(f"   Expires   : {getattr(file_obj, 'expiration_time', 'unknown')}")
    print(f"   Saving to : {output_path}")

    client.files.download(file=file_obj)
    file_obj.save(str(output_path))

    print(f"   Done. Saved to {output_path}")


def cmd_generate(client, args):
    """Generate a video (original generate flow)."""
    # Resolve prompt from --prompt or --prompt-file
    if args.prompt_file:
        if not args.prompt_file.exists():
            print(f"Error: Prompt file not found: {args.prompt_file}")
            sys.exit(1)
        args.prompt = args.prompt_file.read_text().strip()
    elif not args.prompt:
        print("Error: provide --prompt TEXT or --prompt-file PATH")
        sys.exit(1)

    resolution = args.resolution

    # API constraint: native extensions require 720p
    if args.extend and args.extend_method == "video" and resolution != EXTENSION_RESOLUTION:
        print(f"Note: Forcing resolution to {EXTENSION_RESOLUTION} (required for native video extensions, requested: {resolution})")
        resolution = EXTENSION_RESOLUTION

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_dir = Path("outputs") / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'=' * 60}")
    print("VEO 3.1 VIDEO GENERATION")
    print(f"{'=' * 60}")
    print(f"Prompt: {args.prompt}")
    print(f"Resolution: {resolution} | Aspect Ratio: {args.aspect_ratio}")
    if args.extend:
        print(f"Extensions: {args.extend} (auto-generated prompts, method: {args.extend_method})")
    if args.image:
        print(f"Reference image: {args.image}")
    print(f"Output: {output_dir}")
    print(f"{'=' * 60}")

    cost = CostTracker()

    # --style all: generate one image per style into per-style subdirectories
    if args.style == "all":
        if not args.image_only:
            print("Error: --style all is only supported with --image-only")
            sys.exit(1)
        if args.total_images:
            print("Error: --style all cannot be combined with --total-images")
            sys.exit(1)
        all_styles = list(STYLE_DEFINITIONS.keys())
        print(f"\nGenerating {len(all_styles)} styles into: {output_dir}")
        print(f"{'=' * 60}")
        if args.image and not args.image.exists():
            print(f"Error: Reference image not found: {args.image}")
            sys.exit(1)
        all_style_paths = []
        failed_styles = []
        for style_name in all_styles:
            style_dir = output_dir / style_name
            style_dir.mkdir(parents=True, exist_ok=True)
            try:
                print(f"\n[{style_name}] Generating image prompt using {TEXT_MODEL}...")
                img_json = generate_image_prompt_json(client, args.prompt, cost_tracker=cost, style=style_name)
                (style_dir / "image_prompt.json").write_text(img_json)
                print(f"\n--- JSON used for {style_name}/image.png ---")
                print(img_json)
                print(f"---")
                print(f"[{style_name}] Generating image using {IMAGE_MODEL}...")
                if args.image:
                    img_path = generate_image_from_reference(
                        client, img_json, args.image, style_dir, cost_tracker=cost
                    )
                    final = style_dir / "image.png"
                    img_path.rename(final)
                    img_path = final
                else:
                    img_path = generate_image_from_text(client, img_json, style_dir, filename="image.png", cost_tracker=cost)
                print(f"[{style_name}] Saved: {img_path}")
                all_style_paths.append(img_path)
            except Exception as e:
                print(f"[{style_name}] FAILED: {e} — skipping")
                failed_styles.append(style_name)
        if failed_styles:
            print(f"\nFailed styles: {', '.join(failed_styles)}")
        if args.html:
            html_path = render_images_as_html(all_style_paths, output_dir, title=f"{args.prompt} — all styles")
            print(f"\nHTML viewer saved to: {html_path}")
        print(f"\n{'=' * 60}")
        print(f"Output: {output_dir}")
        print(f"{'=' * 60}")
        cost.print_summary()
        return

    # Text-to-image only flow
    if args.image_only:
        # When --comics is set, --total-images means total PAGES; expand to actual image count.
        if args.comics and args.total_images:
            pages = args.total_images
            ppp = optimal_panels_per_page()
            n = pages * ppp
            print(f"\nComics mode: {pages} page(s) × {ppp} panels/page = {n} images to generate")
        else:
            n = args.total_images or 1

        # Generate first prompt from the initial idea
        print(f"\nGenerating image prompt 1 using {TEXT_MODEL}...")
        suffix = f"_1" if n > 1 else ""
        first_json = generate_image_prompt_json(client, args.prompt, cost_tracker=cost, style=args.style)
        (output_dir / f"image_prompt{suffix}.json").write_text(first_json)
        print(f"   Prompt 1 saved to: {output_dir / f'image_prompt{suffix}.json'}")
        first_filename_preview = "image_1.png" if n > 1 else "image.png"
        print(f"\n--- JSON used for {first_filename_preview} ---")
        print(first_json)
        print(f"---")

        # Generate first image — use reference if provided, otherwise text-only
        first_filename = "image_1.png" if n > 1 else "image.png"
        if args.image:
            if not args.image.exists():
                print(f"Error: Reference image not found: {args.image}")
                sys.exit(1)
            print(f"\nGenerating image 1 using {IMAGE_MODEL} (with reference image)...")
            prev_image_path = generate_image_from_reference(
                client, first_json, args.image, output_dir, cost_tracker=cost
            )
            # rename to expected filename
            final_path = output_dir / first_filename
            prev_image_path.rename(final_path)
            prev_image_path = final_path
        else:
            print(f"\nGenerating image 1 using {IMAGE_MODEL}...")
            prev_image_path = generate_image_from_text(
                client, first_json, output_dir, filename=first_filename, cost_tracker=cost
            )
        print(f"   Image 1 saved to: {prev_image_path}")
        prev_json = first_json
        all_image_paths = [prev_image_path]
        all_prompt_jsons = [first_json]

        # Generate images 2-N: each prompt continues from previous, each image uses previous image as reference
        for i in range(2, n + 1):
            print(f"\nGenerating image prompt {i} using {TEXT_MODEL} (continues from prompt {i - 1})...")
            next_json = generate_continuation_prompt_json(client, prev_json, cost_tracker=cost, style=args.style)
            (output_dir / f"image_prompt_{i}.json").write_text(next_json)
            print(f"   Prompt {i} saved to: {output_dir / f'image_prompt_{i}.json'}")
            print(f"\n--- JSON used for image_{i}.png ---")
            print(next_json)
            print(f"---")

            print(f"Generating image {i} using {IMAGE_MODEL} (based on image {i - 1})...")
            img_path = generate_image_variation(
                client, next_json, prev_image_path, output_dir, f"image_{i}.png", cost_tracker=cost
            )
            print(f"   Image {i} saved to: {img_path}")
            prev_json = next_json
            prev_image_path = img_path
            all_image_paths.append(img_path)
            all_prompt_jsons.append(next_json)

        # Compose comics pages if requested — always generate dialog
        if args.comics and len(all_image_paths) > 0:
            print(f"\nGenerating comics dialog...")
            dialog_data = generate_comics_dialog(client, all_prompt_jsons, cost_tracker=cost)
            print(f"\nComposing comics page(s)...")
            compose_comics_pages(all_image_paths, dialog_data, output_dir, style=args.style)

        # Render images into a self-contained HTML file
        if args.html and len(all_image_paths) > 0:
            html_path = render_images_as_html(all_image_paths, output_dir, title=args.prompt)
            print(f"\nHTML viewer saved to: {html_path}")

        print(f"\n{'=' * 60}")
        print(f"Output: {output_dir}")
        print(f"{'=' * 60}")
        cost.print_summary()
        return

    reference_image_path = None

    # Image-to-video flow
    if args.image:
        if not args.image.exists():
            print(f"Error: Reference image not found: {args.image}")
            sys.exit(1)
        if getattr(args, "direct_image", False):
            # Skip intermediate restyle — pass original image directly to Veo for best face fidelity
            reference_image_path = args.image
            print(f"\nUsing reference image directly (no restyle): {reference_image_path}")
        else:
            print(f"\nGenerating styled image from reference using {IMAGE_MODEL}...")
            reference_image_path = generate_image_from_reference(
                client, args.prompt, args.image, output_dir, cost_tracker=cost
            )
            print(f"   Reference image saved to: {reference_image_path}")

    # Generate initial video
    print(f"\n--- Prompt used for video_part_0.mp4 (initial) ---")
    print(args.prompt)
    print(f"---")
    video = generate_video(
        client=client,
        prompt=args.prompt,
        resolution=resolution,
        aspect_ratio=args.aspect_ratio,
        reference_image_path=reference_image_path,
        cost_tracker=cost,
    )

    # Save initial prompt
    (output_dir / "prompt_0.txt").write_text(args.prompt)

    # Generate extensions with auto-generated prompts
    if args.extend and args.extend > 0:
        print(f"\nGenerating {args.extend} extension prompt(s) using {TEXT_MODEL}...")
        extension_prompts = generate_extension_prompts(
            client, args.prompt, args.extend, cost_tracker=cost
        )
        for i, ep in enumerate(extension_prompts, 1):
            print(f"\n--- Prompt used for video_part_{i}.mp4 (extension {i}) ---")
            print(ep)
            print(f"---")
            (output_dir / f"prompt_{i}.txt").write_text(ep)

        video = extend_video_chain(
            client,
            video,
            extension_prompts,
            output_dir,
            resolution,
            args.aspect_ratio,
            args.extend_method,
            cost_tracker=cost
        )

    # Save final video
    output_path = output_dir / "video_final.mp4"
    print(f"\nSaving final video to: {output_path}")
    video.save(str(output_path))

    print(f"\n{'=' * 60}")
    print("COMPLETE")
    print(f"{'=' * 60}")
    print(f"Output: {output_path}")
    print(f"{'=' * 60}")
    cost.print_summary()


def main():
    parser = argparse.ArgumentParser(
        description="Veo 3.1 Video Generation CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
commands:
  generate    Generate a video with Veo 3.1  (default — subcommand optional)
  list        List files stored in your Google Files API account (expire after 48h)
  download    Download a file from your Google Files API account

generate options:
  --prompt TEXT          Video description (or use --prompt-file)
  --prompt-file PATH     Read prompt from a text file
  --resolution CHOICE    720p | 1080p (default) | 4k
                           Note: 1080p and 4k use 8s duration; 720p uses 4s
  --aspect-ratio CHOICE  16:9 (default) | 9:16
  --extend N             Auto-generate N continuation prompts and extend the
                           video by N×7s segments (forces resolution to 720p)
  --image PATH           Reference image: generates a styled image first via
                           Gemini Flash, then passes it to Veo as a reference
  --image-only           Generate a standalone image (no video): TEXT model
                           creates a detailed JSON prompt, IMAGE model renders it
  --total-images N       With --image-only: generate N storyboard images where
                           each continues from the previous (prompt + image)
  --style STYLE          Apply a visual style to all generated images:
                           comics       Bold ink outlines, flat colors, Ben-Day dots, Marvel/DC style
                           pixar        Pixar/Disney 3D CGI, warm lighting, expressive characters
                           film-noir    Black & white, dramatic shadows, 1940s detective mood
                           anime        Japanese anime, cel-shaded, vibrant colors, manga composition
                           watercolor   Soft translucent brush strokes, pastel tones, paper texture
                           studio-ghibli  Hand-painted backgrounds, whimsical, warm nostalgic feel
                           oil-painting Classic impasto texture, chiaroscuro, Old Masters inspired
                           retro-80s    Neon synthwave, vaporwave, Miami Vice color palette
                           retro-50s    Warm Technicolor, atomic age Americana, vintage ad illustration
                           retro-70s    Warm amber/earth tones, analog film grain, Kodachrome palette
                           sci-fi       Epic sci-fi concept art, cosmic lighting, Syd Mead / Mass Effect
                           sport        Peak action freeze-frame, motion blur, ESPN editorial style
  --comics               Compose all generated images into a comics page layout at the end
                           (combine with --style comics to apply comic art style to the images)

download options:
  name                   File name from 'list' output  (e.g. files/abc123)
  --output PATH          Where to save the file (default: auto-named in cwd)

models used:
  veo-3.1-generate-preview          Video generation
  gemini-3.1-pro-preview            Extension prompt generation / image prompt JSON
  gemini-3.1-flash-image-preview    Reference image generation / standalone image

pricing (USD, March 2026):
  Veo 720p / 1080p   $0.40 / second of video
  Veo 4k             $0.60 / second of video
  Gemini Pro text    $2.00 / 1M input tokens · $12.00 / 1M output tokens
  Gemini Flash image $0.50 / 1M input tokens · $60.00 / 1M image output tokens

examples:
  python veo.py --prompt "A cat walking through a sunlit garden" --resolution 720p
  python veo.py --prompt "Ocean waves at sunset" --extend 2 --aspect-ratio 16:9
  python veo.py --prompt "Futuristic cityscape at night" --image ./ref.png
  python veo.py --prompt "tiny workers building a Starbucks frappuccino" --image-only
  python veo.py --prompt "A space battle" --image-only --total-images 6 --style anime --comics
  python veo.py --prompt "A detective in a dark alley" --image-only --style film-noir
  python veo.py --prompt "A fantasy forest" --image-only --total-images 4 --style studio-ghibli
  python veo.py --prompt "A dancer performing ballet" --aspect-ratio 9:16
  python veo.py list
  python veo.py --list
  python veo.py download files/abc123
  python veo.py --download files/abc123 --output my_video.mp4
""",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    # ── generate (default) ──────────────────────────────────────────────
    gen = subparsers.add_parser("generate", help="Generate a video (default command)")
    gen.add_argument("--prompt", type=str, help="Video description (or use --prompt-file)")
    gen.add_argument("--prompt-file", type=Path, metavar="PATH", help="Path to a text file containing the prompt")
    gen.add_argument("--extend", type=int, metavar="N", help="Number of extensions")
    gen.add_argument("--extend-method", type=str, choices=["video", "image"], default="image",
                     help="How to extend: 'video' (seamless but forced 720p) or 'image' (uses last frame as reference, supports 1080p). Default: image")
    gen.add_argument("--image", type=Path, metavar="PATH", help="Reference image path")
    gen.add_argument("--direct-image", action="store_true",
                     help="Pass the reference image directly to Veo without the intermediate restyle step (better face fidelity)")
    gen.add_argument("--image-only", action="store_true", help="Generate a standalone image (no video) from the prompt idea")
    gen.add_argument("--total-images", type=int, metavar="N", help="Generate N images (used with --image-only): first image from text, remaining N-1 from image 1 as reference")
    gen.add_argument(
        "--style",
        type=str,
        choices=list(STYLE_DEFINITIONS.keys()) + ["all"],
        metavar="STYLE",
        help=(
            "Visual style to apply to generated images. "
            "Use 'all' to generate one image per style into a shared output directory (incompatible with --total-images). "
            "Choices: all, " + ", ".join(STYLE_DEFINITIONS.keys())
        ),
    )
    gen.add_argument("--comics", action="store_true", help="Compose generated images into comics page(s) at the end (use --style comics to also apply comic art style)")
    gen.add_argument("--html", action="store_true", help="Render generated image(s) into a self-contained HTML file (images.html) with base64-embedded images")
    gen.add_argument("--aspect-ratio", type=str, choices=["16:9", "9:16"], default="16:9",
                     help="Aspect ratio (default: 16:9)")
    gen.add_argument("--resolution", type=str, choices=["720p", "1080p", "4k"], default="1080p",
                     help="Resolution (default: 1080p)")

    # ── list ────────────────────────────────────────────────────────────
    subparsers.add_parser("list", help="List all files in your Google Files API account")

    # ── download ────────────────────────────────────────────────────────
    dl = subparsers.add_parser("download", help="Download a file from your Google Files API account")
    dl.add_argument("name", type=str, help="File name (e.g. files/abc123)")
    dl.add_argument("--output", type=str, metavar="PATH",
                    help="Save path (default: auto-named in current directory)")

    # --help --style  →  print style descriptions and exit
    argv_set = set(sys.argv[1:])
    if "--style" in argv_set and ("--help" in argv_set or "-h" in argv_set):
        print("Available styles:\n")
        for name, defn in STYLE_DEFINITIONS.items():
            desc = defn.get("description", "")
            print(f"  {name:<18}  {desc}")
        print()
        sys.exit(0)

    # Allow flag-style aliases: --list → list, --download → download
    if len(sys.argv) > 1:
        if sys.argv[1] == "--list":
            sys.argv[1] = "list"
        elif sys.argv[1] == "--download":
            sys.argv[1] = "download"

    # If the first arg isn't a known subcommand, treat the whole invocation as 'generate'
    known_commands = {"generate", "list", "download"}
    if len(sys.argv) > 1 and sys.argv[1] not in known_commands:
        sys.argv.insert(1, "generate")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GOOGLE_API_KEY environment variable not set.")
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    try:
        if args.command == "generate":
            cmd_generate(client, args)
        elif args.command == "list":
            cmd_list(client, args)
        elif args.command == "download":
            cmd_download(client, args)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
