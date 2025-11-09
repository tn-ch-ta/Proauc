import os
import torch
import random
from transformers import pipeline
from moviepy.editor import (
    VideoFileClip, CompositeVideoClip, concatenate_videoclips, TextClip
)
from moviepy.video.fx.all import crop
from tqdm import tqdm
from config import OUTPUT_DIR, MAX_TOTAL_DURATION, ALLOW_CROPPING


# === Initialize TinyLlama for text generation ===
print("🧠 Loading TinyLlama model for funny text generation...")
generator = pipeline(
    "text-generation",
    model="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
    tokenizer="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
    device=0 if torch.cuda.is_available() else -1
)


# === UTILITIES ===
def dynamic_font_size(text, base_size, max_width, char_limit=20):
    """Auto-shrink font for long text."""
    if len(text) <= char_limit:
        return base_size
    shrink_factor = min(1.0, char_limit / len(text))
    return int(base_size * (0.8 + 0.2 * shrink_factor))


# === AI TEXT GENERATION ===
def generate_funny_labels(titles_and_thumbnails):
    """Generate short funny labels for each clip using TinyLlama."""
    print("😂 Generating funny labels using TinyLlama...")
    joined = "\n".join(
        [f"Clip {i+1}: Title = {item['title']}, Thumbnail description = {item['thumbnail']}"
         for i, item in enumerate(titles_and_thumbnails)]
    )

    prompt = (
        "You are a witty YouTube Shorts editor. For each clip below, write a short funny label "
        "(max 4 words) that fits the title and thumbnail description. "
        "Example:\n1. HORSE CHAOS\n2. NPC MOMENT\n3. WILD WEST FAILS\n\nNow respond:\n"
        + joined
    )

    response = generator(
        prompt, max_new_tokens=120, do_sample=True, temperature=0.9
    )[0]["generated_text"]

    lines = [line.strip() for line in response.split("\n") if line.strip() and line[0].isdigit()]
    return lines[:len(titles_and_thumbnails)]


def generate_main_title(titles_and_thumbnails):
    """Generate one bold, clickbait main title."""
    print("🏷️ Generating main title using TinyLlama...")
    joined = "\n".join(
        [f"- {item['title']} ({item['thumbnail']})" for item in titles_and_thumbnails]
    )

    prompt = (
        "You are a viral YouTube editor. Create ONE bold, funny, clickbait-style YouTube Shorts title "
        "summarizing all clips below. Make it all caps, max 10 words. "
        "Example: 'TOP 5 RDR2 FAILS (NPC CHAOS)'.\n\nClips:\n" + joined + "\n\nTitle:"
    )

    response = generator(
        prompt, max_new_tokens=40, do_sample=True, temperature=0.8
    )[0]["generated_text"]

    title = response.split("Title:")[-1].strip().upper()
    return title[:100]


# === VIDEO PROCESSING ===
def make_vertical_clip(video_path, target_width=1080, target_height=1920):
    """Convert clip to 9:16 portrait format."""
    clip = VideoFileClip(video_path)
    w, h = clip.size
    factor = target_width / w
    clip = clip.resize(factor)
    if clip.h > target_height:
        if ALLOW_CROPPING:
            clip = crop(
                clip, height=target_height, width=target_width,
                x_center=clip.w / 2, y_center=clip.h / 2
            )
        else:
            clip = clip.resize(height=target_height)
    return clip.set_position(("center", "center")).resize((target_width, target_height))


def label_clip(clip, label_text, corner="top-left", base_fontsize=70, color="yellow", stroke_color="black"):
    """Overlay a text label on the clip."""
    fontsize = dynamic_font_size(label_text, base_fontsize, clip.w)
    txt = TextClip(
        label_text,
        fontsize=fontsize,
        color=color,
        stroke_color=stroke_color,
        stroke_width=3,
        font="Arial-Bold",
        method="caption"
    ).set_duration(clip.duration)

    margin = 40
    positions = {
        "top-left": (margin, margin),
        "top-right": (clip.w - txt.w - margin, margin),
        "bottom-left": (margin, clip.h - txt.h - margin),
        "bottom-right": (clip.w - txt.w - margin, clip.h - txt.h - margin),
    }
    return CompositeVideoClip([clip, txt.set_position(positions.get(corner, (margin, margin)))])


# === MAIN COMPOSITION FUNCTION ===
def compose_short(clip_data, output_filename="final_short.mp4"):
    """
    Compose a YouTube short using TinyLlama labels & main title.
    clip_data = list of dicts:
      [{"path": "video1.mp4", "title": "...", "thumbnail": "..."}, ...]
    """
    print("\n🎬 Building video from clips...")
    titles_and_thumbnails = [{"title": c["title"], "thumbnail": c["thumbnail"]} for c in clip_data]

    # Generate AI funny labels + main title
    short_labels = generate_funny_labels(titles_and_thumbnails)
    main_title = generate_main_title(titles_and_thumbnails)
    print(f"🎯 Generated main title: {main_title}")

    clips = []
    total = 0

    for i, clip_info in enumerate(tqdm(clip_data, desc="Processing clips", ncols=80)):
        path = clip_info["path"]
        clip = VideoFileClip(path)

        # ✅ Trim long clips (>40s) to 25s
        if clip.duration > 40:
            print(f"✂️ Trimming long clip: {os.path.basename(path)} to 25s")
            clip = clip.subclip(0, 25)

        # Stop if exceeding total duration
        remaining = MAX_TOTAL_DURATION - total
        if remaining <= 0:
            break
        if clip.duration > remaining:
            clip = clip.subclip(0, remaining)

        vclip = make_vertical_clip(path)
        label = short_labels[i] if i < len(short_labels) else f"CLIP {i+1}"
        labelled = label_clip(vclip, label_text=label, corner="top-left")

        clips.append(labelled)
        total += labelled.duration

    if not clips:
        raise RuntimeError("No valid clips to compose.")

    # Combine and overlay title
    final = concatenate_videoclips(clips, method="compose").set_fps(24)

    main_fontsize = dynamic_font_size(main_title, 100, 1080, char_limit=25)
    title_clip = TextClip(
        main_title,
        fontsize=main_fontsize,
        color="yellow",
        stroke_color="black",
        stroke_width=5,
        font="Arial-Bold",
        method="caption"
    ).set_duration(3).set_position(("center", 100))

    final = CompositeVideoClip([final, title_clip])
    output_path = os.path.join(OUTPUT_DIR, output_filename)

    print("💾 Rendering final video (this may take a bit)...")
    final.write_videofile(
        output_path,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        preset="medium"
    )

    print(f"\n✅ Done! Final video saved to: {output_path}")
    return {"path": output_path, "title": main_title}