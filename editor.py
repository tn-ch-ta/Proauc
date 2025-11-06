# editor.py
import os
import tempfile
from moviepy.editor import (
    VideoFileClip, CompositeVideoClip, concatenate_videoclips, TextClip
)
from moviepy.video.fx.all import crop
from config import OUTPUT_DIR, MAX_TOTAL_DURATION, ALLOW_CROPPING
from openai import OpenAI

client = OpenAI()

# === UTILS ===

def dynamic_font_size(text, base_size, max_width, char_limit=20):
    """Reduce font size automatically for long text or limited space."""
    if len(text) <= char_limit:
        return base_size
    shrink_factor = min(1.0, char_limit / len(text))
    return int(base_size * (0.8 + 0.2 * shrink_factor))

# === AUDIO TRANSCRIPTION ===

def extract_audio_transcript(video_path):
    """Extract audio and transcribe using OpenAI Whisper."""
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_audio:
        clip = VideoFileClip(video_path)
        clip.audio.write_audiofile(tmp_audio.name, verbose=False, logger=None)
        clip.close()
        with open(tmp_audio.name, "rb") as f:
            transcription = client.audio.transcriptions.create(
                model="gpt-4o-mini-transcribe",
                file=f
            )
        os.remove(tmp_audio.name)
    return transcription.text.strip()

# === VIDEO FORMATTING ===

def make_vertical_clip(video_path, target_width=1080, target_height=1920):
    """Convert clip to portrait 9:16."""
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
    clip = clip.set_position(("center", "center")).resize((target_width, target_height))
    return clip

# === LABELING ===

def label_clip(clip, label_text, corner="top-left", base_fontsize=70, color="yellow", stroke_color="black"):
    """Add a text label to clip with dynamic font sizing."""
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
    if corner == "top-left":
        txt = txt.set_position((margin, margin))
    elif corner == "top-right":
        txt = txt.set_position((clip.w - txt.w - margin, margin))
    elif corner == "bottom-left":
        txt = txt.set_position((margin, clip.h - txt.h - margin))
    elif corner == "bottom-right":
        txt = txt.set_position((clip.w - txt.w - margin, clip.h - txt.h - margin))
    return CompositeVideoClip([clip, txt])

# === MAIN COMPOSER ===

def compose_short(clip_paths, labels=None, output_filename="final_short.mp4"):
    """Compose a YouTube short with dynamic labels and AI-generated title."""
    transcripts = []
    clips = []
    total = 0

    print("🧠 Transcribing each clip for title generation...")
    for path in clip_paths:
        try:
            text = extract_audio_transcript(path)
            transcripts.append(text)
        except Exception as e:
            print(f"⚠️ Failed to transcribe {path}: {e}")
            transcripts.append("")

    # === Generate per-clip short funny labels ===
    prompt = (
        "You are a witty viral video editor. "
        "Create a very short (max 4 words), funny, clickbait-style title for each clip below. "
        "Number them 1., 2., etc. Example: '1. I NEED MONEY'.\n\n"
    )
    numbered_titles = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt + "\n\n".join(f"Clip {i+1}: {t}" for i, t in enumerate(transcripts))
    ).output_text.strip().splitlines()

    short_labels = [line.strip() for line in numbered_titles if line.strip()]

    # === Generate main video title ===
    title_prompt = (
        "Create one bold, clickbait YouTube Shorts title summarizing all clips below. "
        "Make it in all caps, max 10 words, like 'TOP 5 FUNNY FAILS (GONE WRONG)'."
    )
    main_title = client.responses.create(
        model="gpt-4.1-mini",
        input=title_prompt + "\n\n" + "\n".join(transcripts)
    ).output_text.strip().upper()

    print(f"🎯 Generated main title: {main_title}")
    print("🎬 Building video...")

    # === Build labeled clips ===
    for i, path in enumerate(clip_paths):
        clip = VideoFileClip(path)
        remaining = MAX_TOTAL_DURATION - total
        if remaining <= 0:
            break
        max_clip = min(15, remaining)
        if clip.duration > max_clip:
            clip = clip.subclip(0, max_clip)
        vclip = make_vertical_clip(path)
        label = short_labels[i] if i < len(short_labels) else f"CLIP {i+1}"
        labelled = label_clip(vclip, label_text=label, corner="top-left")
        clips.append(labelled)
        total += labelled.duration

    if not clips:
        raise RuntimeError("No valid clips to compose.")

    final = concatenate_videoclips(clips, method="compose").set_fps(24)

    # === Add Main Title Overlay (top center, 3 sec) ===
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
    final.write_videofile(
        output_path,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        preset="medium"
    )
    return output_path