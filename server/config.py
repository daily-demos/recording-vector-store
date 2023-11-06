"""Module providing primary input and output configuration paths."""
import dataclasses
import os

INDEX_DIR_ENV = 'INDEX_DIR'
TRANSCRIPTS_DIR_ENV = 'TRANSCRIPTS_DIR'
UPLOAD_DIR_ENV = 'UPLOAD_DIR'
RECORDINGS_DIR_ENV = 'RECORDINGS_DIR'


@dataclasses.dataclass
class APIConfig:
    """Class representing third-party API keys and other settings."""
    daily_api_key: str = None
    daily_api_url: str = None
    deepgram_api_key: str = None
    deepgram_model_name: str = None


def get_third_party_config() -> APIConfig:
    """Returns third-party configuration"""
    return APIConfig(
        os.getenv("DAILY_API_KEY"),
        os.getenv("DAILY_API_URL"),
        os.getenv("DEEPGRAM_API_KEY"),
        os.getenv("DEEPGRAM_MODEL_NAME")
    )


def ensure_dirs():
    """Creates required file directories if they do not already exist."""
    ensure_dir(TRANSCRIPTS_DIR_ENV)
    ensure_dir(INDEX_DIR_ENV)
    ensure_dir(UPLOAD_DIR_ENV)
    ensure_dir(RECORDINGS_DIR_ENV)


def ensure_dir(env_name: str):
    """Creates directory based on env variable,
    if said directory does not already exist."""
    directory = os.getenv(env_name)
    if not directory:
        directory = env_name
        os.environ[env_name] = directory

    if not os.path.exists(directory):
        os.makedirs(directory)


def get_transcripts_dir_path() -> str:
    """Returns transcript directory path."""
    return os.path.abspath(os.getenv(TRANSCRIPTS_DIR_ENV))


def get_transcript_file_path(file_name):
    """Returns the destination file path of the transcript file"""
    transcript_file_name = f"{file_name}.txt"
    return os.path.join(get_transcripts_dir_path(), transcript_file_name)


def get_index_dir_path() -> str:
    """Returns the index storage directory path."""
    return os.path.abspath(os.getenv(INDEX_DIR_ENV))


def get_upload_dir_path() -> str:
    """Returns upload directory path."""
    return os.path.abspath(os.getenv(UPLOAD_DIR_ENV))


def get_recordings_dir_path() -> str:
    """Returns recording directory path."""
    return os.path.abspath(os.getenv(RECORDINGS_DIR_ENV))
