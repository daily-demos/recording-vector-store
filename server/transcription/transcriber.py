from abc import ABC, abstractmethod


class Transcriber(ABC):

    @abstractmethod
    def requires_local_audio(self) -> bool:
        pass

    @abstractmethod
    def transcribe(self, recording_url: str = None, audio_path: str = None) -> str:
        pass
