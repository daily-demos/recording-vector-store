"""Module that handles media file operations, like saving uploads, stripping audio,
returning existing uploads,etc."""
import os
import pathlib
from pathlib import Path
from typing import List

import requests
from moviepy.video.io.VideoFileClip import VideoFileClip
from quart.datastructures import FileStorage

from config import get_upload_dir_path, get_recordings_dir_path


async def save_uploaded_file(file: FileStorage):
    """Saves given file to the configured upload directory"""
    file_name = os.path.basename(file.filename)
    file_path = Path(get_upload_video_path(file_name))
    try:
        await file.save(file_path)
        if not os.path.exists(file_path):
            raise Exception("Uploaded file not saved", file_path)
    except Exception as e:
        raise Exception("Failed to save uploaded file") from e


def get_uploaded_file_paths() -> List[str]:
    """Returns paths of all mp4 files in the uploads directory"""
    file_names = []
    for path in pathlib.Path(get_upload_dir_path()).iterdir():
        try:
            if not path.is_file() or path.suffix != ".mp4":
                continue
            with open(path, "r+") as file:
                file_names.append(str(file.name))
            break
        except IOError as e:
            print("File is already open, likely still being written.", e)
    return file_names


def produce_local_audio_from_url(recording_url: str, video_file_name: str):
    """Downloads a recording from the given URL and extracts audio from it"""
    video_path = download_recording(recording_url, video_file_name)
    audio_path = extract_audio(video_path)
    os.remove(video_path)
    return audio_path


def download_recording(recording_url: str, video_file_name: str):
    """Downloads Daily recording"""
    local_file_path = get_recording_video_path(video_file_name)

    # Download recording to UPLOAD dir
    try:
        with open(local_file_path, 'wb') as f:
            # Use a single session to persist HTTP connections, avoiding
            # superfluous round-trips.
            session = requests.Session()
            res = session.get(recording_url, stream=True)
            res.raise_for_status()
            for chunk in res.iter_content(1024 * 250):
                f.write(chunk)
            return local_file_path
    except Exception as e:
        raise Exception('failed to download Daily recording') from e


def extract_audio(video_path: str):
    """Extracts audio from given MP4 file"""
    audio_path = get_audio_path(video_path)
    try:
        video = VideoFileClip(video_path)
        video.audio.write_audiofile(audio_path)
    except Exception as e:
        raise Exception('failed to save extracted audio file',
                        video_path, audio_path) from e
    return audio_path


def get_upload_video_path(file_name: str) -> str:
    """Returns video path for a given file name"""
    video_path = os.path.join(get_upload_dir_path(), file_name)
    return video_path


def get_recording_video_path(file_name: str) -> str:
    """Returns video path for a given file name"""
    video_path = os.path.join(get_upload_dir_path(), f'{file_name}.mp4')
    return video_path


def get_audio_path(video_path: str) -> str:
    """Returns audio path for a given file name"""
    audio_dir = os.path.dirname(video_path)
    file_name = pathlib.Path(video_path).stem
    audio_path = os.path.join(audio_dir, f'{file_name}.wav')
    return audio_path


def get_remote_recording_audio_path(file_name: str) -> str:
    """Returns audio path for remote Daily recording"""
    return os.path.join(get_recordings_dir_path(), f"{file_name}.wav")
