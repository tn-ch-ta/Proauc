# fetchers/youtube_fetcher.py
import os
import re
import json
import random
from googleapiclient.discovery import build
from datetime import datetime, timedelta, timezone

# === CONFIG ===
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
SEEN_VIDEOS_FILE = "data/seen_videos.json"  # store previously used videos

# === HELPERS ===
def parse_iso_duration(duration_str):
    """Convert ISO 8601 duration (e.g., PT45S, PT1M2S) to seconds."""
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration_str)
    if not match:
        return 0
    hours = int(match.group(1)) if match.group(1) else 0
    minutes = int(match.group(2)) if match.group(2) else 0
    seconds = int(match.group(3)) if match.group(3) else 0
    return hours * 3600 + minutes * 60 + seconds


def load_seen_videos():
    """Load list of previously used video IDs."""
    if os.path.exists(SEEN_VIDEOS_FILE):
        with open(SEEN_VIDEOS_FILE, "r") as f:
            try:
                return set(json.load(f))
            except json.JSONDecodeError:
                return set()
    return set()


def save_seen_videos(video_ids):
    """Save list of used video IDs."""
    os.makedirs(os.path.dirname(SEEN_VIDEOS_FILE), exist_ok=True)
    with open(SEEN_VIDEOS_FILE, "w") as f:
        json.dump(list(video_ids), f, indent=2)


# === MAIN FUNCTION ===
def search_youtube_short_videos(
    tags=("rdr2", "reddeadredemption2", "rdro"),
    max_results=50,
    max_total_duration=61,
    min_likes=1000,
    max_clips=3
):
    """
    Search for RDR2-related short YouTube videos with:
    - Minimum 1000 likes
    - Published AT LEAST 60 days ago
    - Duration ≤ 61s
    - Maximum of 5 clips returned
    - Skips any previously used videos
    """
    if not YOUTUBE_API_KEY:
        print("⚠️ Missing YOUTUBE_API_KEY in environment variables.")
        return []

    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    seen_videos = load_seen_videos()

    # ✅ Only look for videos published at least 60 days ago
    published_before = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()

    query = " OR ".join(tags)
    print(f"🔍 Searching YouTube for RDR2-related shorts ({query})...")

    # 1️⃣ Search for short videos with relevant tags
    search_req = youtube.search().list(
        part="snippet",
        q=query,
        type="video",
        videoDuration="short",
        maxResults=max_results,
        publishedBefore=published_before,
        relevanceLanguage="en",
        order="viewCount",
    )
    search_res = search_req.execute()
    video_ids = [item["id"]["videoId"] for item in search_res.get("items", [])]

    if not video_ids:
        print("⚠️ No search results found.")
        return []

    # 2️⃣ Get full video details (duration, stats)
    video_req = youtube.videos().list(
        part="snippet,contentDetails,statistics",
        id=",".join(video_ids)
    )
    video_res = video_req.execute()

    # 3️⃣ Filter and format results
    items = []
    for vid in video_res.get("items", []):
        video_id = vid["id"]

        # skip already used
        if video_id in seen_videos:
            continue

        title = vid["snippet"]["title"]
        duration = parse_iso_duration(vid["contentDetails"]["duration"])
        published = vid["snippet"]["publishedAt"]
        stats = vid.get("statistics", {})
        like_count = int(stats.get("likeCount", 0))

        # Filter by likes & duration
        if like_count < min_likes:
            continue
        if duration == 0 or duration > 58:
            continue

        # Confirm it’s relevant to RDR2
        tags_in_video = vid["snippet"].get("tags", [])
        tags_combined = (title + " " + " ".join(tags_in_video)).lower()
        if not any(tag in tags_combined for tag in tags):
            continue

        items.append({
            "title": title,
            "videoId": video_id,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "duration": duration,
            "publishedAt": published,
            "likeCount": like_count,
            "source": "youtube"
        })

    if not items:
        print("⚠️ No videos passed filters.")
        return []

    # 4️⃣ Pick up to max_clips
    random.shuffle(items)
    chosen = items[:max_clips]

    # 5️⃣ Remember used video IDs
    used = seen_videos.union({v["videoId"] for v in chosen})
    save_seen_videos(used)

    print(f"✅ Selected {len(chosen)} RDR2 YouTube clips totaling {sum(v['duration'] for v in chosen)}s")
    print(f"✅ All videos have ≥ {min_likes} likes and are at least 60 days old.")
    print(f"🧠 Remembered {len(used)} total seen videos.")
    return chosen
