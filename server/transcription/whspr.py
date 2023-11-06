"""This module implements Whisper transcription with a locally-downloaded model."""
from enum import Enum

import whisper
from .transcriber import Transcriber


class Models(Enum):
    """Class of basic Whisper model selection options"""
    TINY = "tiny"
    BASE = "base"
    MEDIUM = "medium"
    NBAILAB_LARGE_V2 = "NbAiLab/whisper-large-v2-nob"


class WhisperTranscriber(Transcriber):
    """Class to transcribe an audio file with a locally-downloaded Whisper model"""

    def requires_local_audio(self) -> bool:
        return True

    def transcribe(self, recording_url: str = None,
                   audio_path: str = None) -> str:
        """Transcribes given audio file using Whisper"""
        audio = whisper.load_audio(audio_path)
        model = whisper.load_model(Models.BASE.value, device="cpu")
        transcription = whisper.transcribe(
            model,
            audio
        )
        return transcription["text"]
