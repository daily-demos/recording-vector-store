"""Module defining a transcriber base class, which new transcribers can implement"""
from abc import ABC, abstractmethod


class Transcriber(ABC):
    @abstractmethod
    def requires_local_audio(self) -> bool:
        """Returns whether this transcriber can work with a cloud recording URL
        or if it requires a local audio file to be transferred."""
        pass

    @abstractmethod
    def transcribe(self, recording_url: str = None, audio_path: str = None) -> str:
        """Returns a transcription string"""
        pass
