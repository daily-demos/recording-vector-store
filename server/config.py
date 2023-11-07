"""Module providing primary input and output configuration paths."""
import os

INDEX_DIR_ENV = 'INDEX_DIR'
TRANSCRIPTS_DIR_ENV = 'TRANSCRIPTS_DIR'
UPLOAD_DIR_ENV = 'UPLOAD_DIR'
RECORDINGS_DIR_ENV = 'RECORDINGS_DIR'


class Config:
    """Class representing third-party API keys and other settings."""
    _daily_api_key: str = None
    _daily_api_url: str = None
    _deepgram_api_key: str = None
    _deepgram_model_name: str = None

    _index_dir_path: str = None
    _transcripts_dir_path: str = None
    _uploads_dir_path: str = None
    _recordings_dir_path: str = None

    def __init__(self, daily_api_key=os.getenv("DAILY_API_KEY"),
                 daily_api_url=os.getenv("DAILY_API_URL"),
                 deepgram_api_key=os.getenv("DEEPGRAM_API_KEY"),
                 deepgram_model_name=os.getenv("DEEPGRAM_MODEL_NAME"),
                 index_dir=None,
                 transcripts_dir=None,
                 uploads_dir=None,
                 recordings_dir=None
                 ):

        self._daily_api_key = daily_api_key
        self._daily_api_url = daily_api_url
        self._deepgram_api_key = deepgram_api_key
        self._deepgram_model_name = deepgram_model_name

        if not index_dir:
            self._index_dir_path = os.path.abspath(
                deduce_dir_name("INDEX_DIR"))

        if not transcripts_dir:
            self._transcripts_dir_path = os.path.abspath(
                deduce_dir_name("TRANSCRIPTS_DIR"))

        if not uploads_dir:
            self._uploads_dir_path = os.path.abspath(
                deduce_dir_name("UPLOADS_DIR"))

        if not recordings_dir:
            self._recordings_dir_path = os.path.abspath(
                deduce_dir_name("RECORDINGS_DIR"))

    def ensure_dirs(self):
        """Creates required file directories if they do not already exist."""
        ensure_dir(self._transcripts_dir_path)
        ensure_dir(self._recordings_dir_path)
        ensure_dir(self._uploads_dir_path)
        ensure_dir(self._index_dir_path)

    @property
    def daily_api_key(self) -> str:
        return self._daily_api_key

    @property
    def daily_api_url(self) -> str:
        return self._daily_api_url

    @property
    def deepgram_api_key(self) -> str:
        return self._deepgram_api_key

    @property
    def deepgram_model_name(self) -> str:
        return self._deepgram_model_name

    @property
    def transcripts_dir_path(self) -> str:
        """Returns transcript directory path."""
        return self._transcripts_dir_path

    @property
    def index_dir_path(self) -> str:
        """Returns transcript directory path."""
        return self._index_dir_path

    @property
    def uploads_dir_path(self) -> str:
        """Returns transcript directory path."""
        return self._uploads_dir_path

    @property
    def recordings_dir_path(self) -> str:
        """Returns transcript directory path."""
        return self._recordings_dir_path

    def get_transcript_file_path(self, file_name: str) -> str:
        """Returns the destination file path of the transcript file"""
        return os.path.join(self.transcripts_dir_path, f"{file_name}.txt")

    def get_remote_recording_audio_path(self, file_name: str) -> str:
        """Returns audio path for remote Daily recording"""
        return os.path.join(self.recordings_dir_path, f"{file_name}.wav")


def ensure_dir(dir_path: str):
    """Creates directory at the given path if it does not already exist."""
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)


def deduce_dir_name(env_name: str):
    d = os.getenv(env_name)
    if not d:
        d = env_name
    return d
