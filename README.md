# 🤖 Proauc – The Automated YouTube Shorts Creator

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![YouTube API](https://img.shields.io/badge/API-YouTube_Data_API_v3-red)
![OpenAI](https://img.shields.io/badge/OpenAI-Whisper_&_GPT-orange)
![Status](https://img.shields.io/badge/status-Active-success)

> 🎬 *Search, download, edit, and upload trending shorts — all in one run.*

Proauc is a Python automation system that finds trending short videos from **YouTube**, automatically edits them into one vertical short, generates **AI-based titles and clip labels**, and uploads them directly to your YouTube channel.

---

## 🎬 What It Does

When you run the program once, it will:

1. 🔍 **Search** multiple platforms (YouTube + Reddit) for trending short videos.
2. 🎥 **Select** a random set of 4–8 short clips that are under 58 seconds each.
3. ⬇️ **Download** the clips locally using `yt-dlp`.
4. ✂️ **Edit & Combine** them vertically (9:16) using `moviepy`.
5. 🧠 **Transcribe & Title** each clip automatically using the OpenAI API (Whisper + GPT):
   - Generates a **main funny clickbait title** for the compilation.
   - Generates **short witty labels** for each clip (displayed top-left on screen).
6. ☁️ **Upload** the final video automatically to your YouTube channel using the YouTube Data API.
7. 🧾 **Log** results and display progress in your console.

--