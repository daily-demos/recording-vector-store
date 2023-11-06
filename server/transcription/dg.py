"""This module implements Deepgram transcription
"""
import os

from deepgram import Deepgram

from .transcriber import Transcriber


class DeepgramTranscriber(Transcriber):
    """Class to transcribe a recording from either a local audio file
    or a remote URL with Deepgram"""
    api_key = None
    model_name = None

    def __init__(self, api_key: str, model_name: str):
        self.api_key = api_key
        self.model_name = model_name
        if not self.model_name:
            self.model_name = "nova"

    def requires_local_audio(self) -> bool:
        return False

    def get_transcription_options(self):
        """Compiles the Deepgram transfiguration config"""
        return {
            "model": self.model_name,
            "filler_words": True,
            "language": "en",
        }

    def transcribe(self, recording_url: str = None,
                   audio_path: str = None) -> str:
        """Transcribes give audio file or recording URL"""
        deepgram_api_key = self.api_key
        if not deepgram_api_key:
            raise Exception("Deepgram API key is missing")
        if not recording_url and not audio_path:
            raise Exception(
                "Either recording URL or local audio path must be specified")

        if recording_url and audio_path:
            print(
                "Both recording URL and audio path specified. Favoring local audio path.")

        if audio_path:
            return self.transcribe_from_file(deepgram_api_key, audio_path)
        return self.transcribe_from_url(deepgram_api_key, recording_url)

    def transcribe_from_url(self, api_key: str, recording_url: str) -> str:
        """Transcribers recording from URL."""
        print("transcribing from URL:", recording_url)
        deepgram = Deepgram(api_key)
        source = {'url': recording_url}
        res = deepgram.transcription.sync_prerecorded(
            source, self.get_transcription_options()
        )
        return self.get_transcript(res)

    def transcribe_from_file(self, api_key: str, audio_path: str) -> str:
        """Transcribes recording from audio file."""
        if audio_path and not os.path.exists(audio_path):
            raise Exception("Audio file could not be found", audio_path)
        deepgram = Deepgram(api_key)

        with open(audio_path, 'rb') as audio_file:
            source = {'buffer': audio_file, 'mimetype': "audio/wav"}
            res = deepgram.transcription.sync_prerecorded(
                source, self.get_transcription_options()
            )
        return self.get_transcript(res)

    def get_transcript(self, result) -> str:
        """Retrieves transcript string from Deepgram result"""
        res = result["results"]
        channels = res["channels"]
        channel = channels[0]
        alts = channel["alternatives"]
        alt = alts[0]
        return alt["transcript"]
