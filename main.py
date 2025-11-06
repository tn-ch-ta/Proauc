# main.py
import random
from fetchers import reddit_fetcher, youtube_fetcher
from downloaders.downloader import download_with_ytdlp
from editor import compose_short
from titlegen import generate_title
from uploader import upload_video

from config import MIN_CLIPS, MAX_CLIPS

def pick_random_candidates(candidates, min_n=4, max_n=8):
    n = random.randint(min_n, max_n)
    return random.sample(candidates, min(n, len(candidates)))

def simple_label_from_title(title, index):
    # derive a short label (like shown in screenshot), e.g., "4. I NEED MONEY"
    short = title.split(" - ")[0]
    short = (short[:20] + "...") if len(short) > 20 else short
    return f"{index+1}. {short.upper()}"

def main():
    # 1) Fetch candidates from multiple sources
    reddit_cands = reddit_fetcher.find_video_posts(limit=60)
    yt_cands = youtube_fetcher.search_youtube_short_videos(q="funny cringe short", max_results=30)
    candidates = reddit_cands + yt_cands
    if not candidates:
        print("No candidates found. Check API keys and connectivity.")
        return
    picked = pick_random_candidates(candidates, MIN_CLIPS, MAX_CLIPS)
    print("Picked", len(picked), "clips")
    # 2) Download them with yt-dlp
    downloaded_paths = []
    labels = []
    for i, cand in enumerate(picked):
        try:
            p = download_with_ytdlp(cand["url"], filename_prefix=f"clip{i}")
            downloaded_paths.append(p)
            labels.append(simple_label_from_title(cand.get("title","clip"), i))
        except Exception as e:
            print("Download failed for", cand.get("url"), e)
    if not downloaded_paths:
        print("Nothing downloaded.")
        return
    # 3) Edit / compose into a single short
    output_path = compose_short(downloaded_paths, labels, output_filename="final_short.mp4")
    print("Final short created at", output_path)
    # 4) Generate title
    title = generate_title(labels)
    print("Generated title:", title)
    # 5) Upload to YouTube
    response = upload_video(output_path, title, description="Automated compilation", tags=["shorts","compilation"], privacy="public")
    print("Upload response:", response)

if __name__ == "__main__":
    main()
