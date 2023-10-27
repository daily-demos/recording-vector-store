import os
from pathlib import Path

import requests
from moviepy.video.io.VideoFileClip import VideoFileClip

from config import get_upload_dir_path

def produce_local_audio_from_url(recording_url: str, video_file_name: str):
    video_path = download_recording(recording_url, video_file_name)
    audio_path = extract_audio(video_path, video_file_name)
    os.remove(video_path)
    return audio_path

def download_recording(recording_url: str, video_file_name: str):
    print("recording_url:", recording_url)
    # Download recording to UPLOAD dir
    try:
        local_file_path = get_video_path(video_file_name)

        with open(local_file_path, 'wb') as f:
            # Use a single session to persist HTTP connections, avoiding
            # superfluous round-trips.
            session = requests.Session()
            res = session.get(recording_url, stream=True)
            res.raise_for_status()
            print(f"Fetching {recording_url}")
            for chunk in res.iter_content(1024 * 250):
                print(f"Writing chunk...")
                f.write(chunk)
            return local_file_path
    except Exception as e:
        raise Exception('failed to download Daily recording') from e


def extract_audio(video_path: str, file_name: str):
    """Extracts audio from given MP4 file"""
    audio_path = get_audio_path(file_name)
    try:
        video = VideoFileClip(video_path)
        video.audio.write_audiofile(audio_path)
    except Exception as e:
        raise Exception('failed to save extracted audio file',
                        video_path, audio_path) from e
    return audio_path


def get_video_path(file_name: str) -> str:
    video_path = os.path.join(get_upload_dir_path(), f'{file_name}.mp4')
    return video_path

def get_audio_path(file_name: str) -> str:
    audio_path = os.path.join(get_upload_dir_path(), f'{file_name}.wav')
    return audio_path