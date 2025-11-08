import os
import tempfile
import torch
import whisper
from transformers import pipeline
from moviepy.editor import (
    VideoFileClip, CompositeVideoClip, concatenate_videoclips, TextClip
)
from moviepy.video.fx.all import crop
from tqdm import tqdm
from config import OUTPUT_DIR, MAX_TOTAL_DURATION, ALLOW_CROPPING

# === Initialize Models (once) ===
print("🧩 Loading local Whisper model for transcription...")
whisper_model = whisper.load_model("base")  # or "small" / "medium" for higher quality

print("🧠 Loading TinyLlama model for funny text generation...")
generator = pipeline(
    "text-generation",
    model="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
    tokenizer="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
    device=0 if torch.cuda.is_available() else -1
)


# === UTILS ===
def dynamic_font_size(text, base_size, max_width, char_limit=20):
    """Reduce font size automatically for long text or limited space."""
    if len(text) <= char_limit:
        return base_size
    shrink_factor = min(1.0, char_limit / len(text))
    return int(base_size * (0.8 + 0.2 * shrink_factor))


# === AUDIO TRANSCRIPTION ===
def extract_audio_transcript(video_path):
    """Extract audio and transcribe using local Whisper."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_audio:
        clip = VideoFileClip(video_path)
        clip.audio.write_audiofile(tmp_audio.name, verbose=False, logger=None)
        clip.close()

        print(f"🎤 Transcribing audio from: {os.path.basename(video_path)} ...")
        result = whisper_model.transcribe(tmp_audio.name, fp16=False)

        os.remove(tmp_audio.name)
    return result["text"].strip()


# === TEXT GENERATION HELPERS ===
def generate_funny_labels(transcripts):
    """Use TinyLlama to generate short funny labels for each clip."""
    print("😂 Generating funny labels using TinyLlama...")
    joined = "\n".join([f"Clip {i+1}: {t}" for i, t in enumerate(transcripts)])
    prompt = (
        "You are a witty viral video editor. Create a short funny label (max 4 words) "
        "for each clip below. Number them 1., 2., etc. Example:\n"
        "1. I NEED MONEY\n2. CATS BE LIKE\n\nNow respond:\n" + joined
    )

    # Show progress bar simulation during generation
    print("⚙️ Generating responses (this might take a moment)...")
    for _ in tqdm(range(40), desc="TinyLlama generating", ncols=80):
        torch.cuda.synchronize() if torch.cuda.is_available() else None

    response = generator(prompt, max_new_tokens=100, do_sample=True, temperature=0.9)[0]["generated_text"]

    lines = [line.strip() for line in response.split("\n") if line.strip() and line[0].isdigit()]
    return lines[:len(transcripts)]


def generate_main_title(transcripts):
    """Use TinyLlama to generate a bold clickbait YouTube title."""
    print("🏷️ Generating main title using TinyLlama...")
    joined = "\n".join(transcripts)
    prompt = (
        "Create ONE bold, clickbait-style YouTube Shorts title summarizing all clips below. "
        "Make it in ALL CAPS, max 10 words, like 'TOP 5 FUNNY FAILS (GONE WRONG)'.\n\n"
        f"{joined}\n\nTitle:"
    )

    for _ in tqdm(range(30), desc="TinyLlama title gen", ncols=80):
        torch.cuda.synchronize() if torch.cuda.is_available() else None

    response = generator(prompt, max_new_tokens=30, do_sample=True, temperature=0.8)[0]["generated_text"]
    title = response.split("Title:")[-1].strip().upper()
    return title[:100]


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
    """Compose a YouTube short with local AI transcription & TinyLlama labeling."""
    transcripts = []
    clips = []
    total = 0

    print("\n🧠 Transcribing clips locally with Whisper...")
    for path in tqdm(clip_paths, desc="Transcribing clips", ncols=80):
        try:
            text = extract_audio_transcript(path)
            transcripts.append(text)
        except Exception as e:
            print(f"⚠️ Failed to transcribe {path}: {e}")
            transcripts.append("")

    short_labels = generate_funny_labels(transcripts)
    main_title = generate_main_title(transcripts)
    print(f"🎯 Generated main title: {main_title}")
    print("🎬 Building final video...")

    for i, path in enumerate(tqdm(clip_paths, desc="Processing clips", ncols=80)):
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
    print("💾 Writing final video file (this can take a bit)...")
    final.write_videofile(
        output_path,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        preset="medium"
    )
    output_path.ai_generated_title = main_title
    print(f"\n✅ Done! Final video saved to: {output_path}")
    return output_path