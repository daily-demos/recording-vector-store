"""This module implements Deepgram transcription and filler word removal split point detection
"""
import os

from deepgram import Deepgram
from .transcriber import Transcriber


class DeepgramTranscriber(Transcriber):
    """Class to transcribe a recording from either a local audio file
    or a remote URL with Deepgram"""

    def requires_local_audio(self) -> bool:
        return False

    def get_transcription_options(self):
        """Compiles the Deepgram transfiguration config"""
        return {
            "model": self.get_model_name(),
            "filler_words": True,
            "language": "en",
        }

    def get_model_name(self):
        """Returns the Deepgram model name to use, defaulting to nova"""
        model_name = os.getenv("DEEPGRAM_MODEL_NAME")
        if not model_name:
            model_name = "nova"
        return model_name

    def transcribe(self, recording_url: str = None, audio_path: str = None) -> str:
        """Transcribes give audio file or recording URL"""
        deepgram_api_key = os.getenv("DEEPGRAM_API_KEY")
        if not deepgram_api_key:
            raise Exception("Deepgram API key is missing")
        if not recording_url and not audio_path:
            raise Exception("Either recording URL or local audio path must be specified")

        if recording_url and audio_path:
            print("Both recording URL and audio path specified. Favoring local audio path.")

        if audio_path:
            return self.transcribe_from_file(deepgram_api_key, audio_path)
        return self.transcribe_from_url(deepgram_api_key, recording_url)

    def transcribe_from_url(self, api_key: str, recording_url: str) -> str:
        """Transcribers recording from URL."""
        print("transcribing from URL:", recording_url)
        deepgram = Deepgram(api_key)
        source = {'url': recording_url}
        try:
            res = deepgram.transcription.sync_prerecorded(
                source, self.get_transcription_options()
            )
            return self.get_transcript(res)
        except Exception as e:
            raise Exception("failed to transcribe from URL") from e

    def transcribe_from_file(self, api_key: str, audio_path: str) -> str:
        """Transcribes recording from audio file."""
        if audio_path and not os.path.exists(audio_path):
            raise Exception("Audio file could not be found", audio_path)
        deepgram = Deepgram(api_key)

        try:
            with open(audio_path, 'rb') as audio_file:
                source = {'buffer': audio_file, 'mimetype': "audio/wav"}
                res = deepgram.transcription.sync_prerecorded(
                    source, self.get_transcription_options()
                )
            return self.get_transcript(res)
        except Exception as e:
            raise Exception("failed to transcribe from local audio path") from e

    def get_transcript(self, result) -> str:
        """Retrieves transcript string from Deepgram result"""
        res = result["results"]
        channels = res["channels"]
        channel = channels[0]
        alts = channel["alternatives"]
        alt = alts[0]
        return alt["transcript"]
