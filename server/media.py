import dataclasses
import os
import pathlib
from enum import Enum
from pathlib import Path
from typing import List, Generator

import requests
from moviepy.video.io.VideoFileClip import VideoFileClip
from quart.datastructures import FileStorage

from config import get_upload_dir_path


async def save_uploaded_file(file: FileStorage):
    print("file name:", file.filename)
    file_name = os.path.basename(file.filename)

    file_path = Path(os.path.join(get_upload_dir_path(), file_name))
    try:
        await file.save(file_path)
        if not os.path.exists(file_path):
            raise Exception("Uploaded file not saved", file_path)
    except Exception as e:
        raise Exception("Failed to save uploaded file") from e


def get_uploaded_file_paths() -> List[str]:
    file_names = []
    for path in pathlib.Path(get_upload_dir_path()).iterdir():
        try:
            print("suffix:", path.suffix, path)
            if not path.is_file() or path.suffix != ".mp4":
                continue
            file = open(path, "r+")  # or "a+", whatever you need
            print("path:", file)
            file_names.append(str(file.name))
            print("got file:", file.name)
            file.close()
            break  # exit the loop
        except IOError as e:
            print("File is already open", e)
    return file_names


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
