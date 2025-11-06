# uploader.py
import os
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle
from googleapiclient.http import MediaFileUpload
from config import YOUTUBE_CLIENT_SECRETS_FILE

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def get_authenticated_service():
    creds = None
    token_path = "youtube_token.pickle"
    if os.path.exists(token_path):
        with open(token_path, "rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(YOUTUBE_CLIENT_SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "wb") as f:
            pickle.dump(creds, f)
    return build("youtube", "v3", credentials=creds)

def upload_video(file_path, title, description="", tags=None, privacy="private"):
    youtube = get_authenticated_service()
    body = {"snippet": {"title": title, "description": description, "tags": tags or [], "categoryId": "22"},
            "status": {"privacyStatus": privacy}}
    media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload progress: {int(status.progress() * 100)}%")
    return response
