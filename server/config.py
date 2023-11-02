"""Module providing primary input and output configuration paths."""

import os

INDEX_DIR_ENV = 'INDEX_DIR'
TRANSCRIPTS_DIR_ENV = 'TRANSCRIPTS_DIR'
UPLOAD_DIR_ENV = 'UPLOAD_DIR'


def ensure_dirs():
    """Creates required file directories if they do not already exist."""
    ensure_dir(TRANSCRIPTS_DIR_ENV)
    ensure_dir(INDEX_DIR_ENV)
    ensure_dir(UPLOAD_DIR_ENV)


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


def get_index_dir_path() -> str:
    """Returns the index storage directory path."""
    return os.path.abspath(os.getenv(INDEX_DIR_ENV))


def get_upload_dir_path() -> str:
    """Returns upload directory path."""
    return os.path.abspath(os.getenv(UPLOAD_DIR_ENV))
