# main.py
import random
from fetchers.youtube_fetcher import search_youtube_short_videos
from downloaders.downloader import download_with_ytdlp
from editor import compose_short
from titlegen import generate_title
from uploader import upload_video

from config import MIN_CLIPS, MAX_CLIPS

def simple_label_from_title(title, index):
    """Generate a label for each clip (like '4. I NEED MONEY')."""
    short = title.split(" - ")[0]
    short = (short[:20] + "...") if len(short) > 20 else short
    return f"{index + 1}. {short.upper()}"

def main():
    print("🔍 Searching YouTube for trending funny/viral shorts...")
    # Fetch curated videos from YouTube only
    yt_videos = search_youtube_short_videos(
        tags=("short", "funny", "viral"),
        max_results=50,
        max_total_duration=58,
        min_clips=MIN_CLIPS,
        max_clips=MAX_CLIPS,
    )

    if not yt_videos:
        print("❌ No suitable YouTube shorts found. Exiting.")
        return

    print(f"✅ Found {len(yt_videos)} clips within duration limit.")
    for i, v in enumerate(yt_videos, start=1):
        print(f"   {i}. {v['title']} ({v['duration']}s)")

    # 2️⃣ Download the selected clips
    downloaded_paths = []
    labels = []
    for i, vid in enumerate(yt_videos):
        try:
            print(f"⬇️  Downloading clip {i + 1}/{len(yt_videos)}: {vid['title']}")
            path = download_with_ytdlp(vid["url"], filename_prefix=f"clip{i}")
            downloaded_paths.append(path)
            labels.append(simple_label_from_title(vid.get("title", "clip"), i))
        except Exception as e:
            print(f"⚠️  Failed to download {vid.get('url')}: {e}")

    if not downloaded_paths:
        print("❌ No clips were successfully downloaded.")
        return

    # 3️⃣ Compose into one vertical short
    print("🎬 Editing and compiling video...")
    output_path = compose_short(downloaded_paths, labels, output_filename="final_short.mp4")
    print(f"✅ Final short created at: {output_path}")

    # 4️⃣ Generate a funny title
    title = generate_title(labels)
    print(f"📝 Generated title: {title}")

    # 5️⃣ Upload to YouTube
    print("📤 Uploading to YouTube...")
    response = upload_video(
        file_path=output_path,
        title=title,
        description="Automated compilation of trending funny viral shorts.",
        tags=["shorts", "funny", "viral", "compilation"],
        privacy="public"
    )
    print("✅ Upload completed.")
    print("Response:", response)

if __name__ == "__main__":
    main()