"""This module implements Whisper transcription with a locally-downloaded model."""
from enum import Enum

import whisper

from .transcriber import Transcriber

DOWNLOAD_DIR_ENV = "WHISPER_DOWNLOAD_DIR"


class Models(Enum):
    """Class of basic Whisper model selection options"""
    TINY = "tiny"
    BASE = "base"
    MEDIUM = "medium"
    NBAILAB_LARGE_V2 = "NbAiLab/whisper-large-v2-nob"


class WhisperTranscriber(Transcriber):

    def requires_local_audio(self) -> bool:
        return True

    def transcribe(self, recording_url: str = None, audio_path: str = None) -> str:
        """Transcribes given audio file using Whisper"""
        try:
            audio = whisper.load_audio(audio_path)
            model = whisper.load_model(Models.BASE.value, device="cpu")
            transcription = whisper.transcribe(
                model,
                audio
            )
        except Exception as e:
            raise Exception("failed to transcribe with Whisper") from e

        return transcription["text"]
