"""This module generates transcripts from the configured Daily domain's recordings
and uses them to create a query-able vector store."""
import asyncio
import dataclasses
import os.path
import pathlib
import sys
import traceback

from enum import Enum

import chromadb
from llama_index import VectorStoreIndex, SimpleDirectoryReader, StorageContext, \
    Response, load_index_from_storage, Document
from llama_index.embeddings import HuggingFaceEmbedding
from llama_index.indices.base import BaseIndex
from llama_index.storage.docstore import SimpleDocumentStore
from llama_index.storage.index_store import SimpleIndexStore
from llama_index.vector_stores import ChromaVectorStore

from config import get_transcripts_dir_path, get_index_dir_path
from daily import fetch_recordings, get_access_link, Recording
from media import (produce_local_audio_from_url, get_audio_path,
                   extract_audio, get_uploaded_file_paths, \
                   get_remote_recording_audio_path)
from transcription.dg import DeepgramTranscriber
from transcription.whspr import WhisperTranscriber
from transcription.transcriber import Transcriber


class State(str, Enum):
    """Class representing index status."""
    UNINITIALIZED = "uninitialized"
    CREATING = "creating"
    UPDATING = "updating"
    LOADING = "loading"
    READY = "ready"
    ERROR = "failed"


class Source(Enum):
    """Class representing sources of the videos to index"""
    DAILY = "daily"
    UPLOADS = "uploads"


@dataclasses.dataclass
class Status:
    """Class representing current index status and a descriptive message"""
    state: str
    message: str


class Store:
    """Class that manages all vector store indexing operations and status updates."""
    status = Status(State.UNINITIALIZED.value, "The store is uninitialized")
    index: BaseIndex = None
    transcriber: Transcriber = None
    collection_name = "my_first_collection"

    # Daily-related properties
    daily_room_name: str = None
    max_videos: int = None

    def __init__(
            self,
            daily_room_name: str = None,
            max_videos: int = None,
            transcriber: Transcriber = None):
        self.daily_room_name = daily_room_name
        self.max_videos = max_videos
        if not transcriber:
            # Default to local Whisper model if Deepgram API key is not
            # specified
            transcriber = WhisperTranscriber()
            deepgram_api_key = os.getenv("DEEPGRAM_API_KEY")
            if deepgram_api_key:
                transcriber = DeepgramTranscriber()
        self.transcriber = transcriber

    def query(self, query: str) -> Response:
        """Queries the existing index, if one exists."""
        if not self.ready():
            raise Exception("Index not yet initialized. Try again later")
        engine = self.index.as_query_engine()
        response = engine.query(query)
        return response

    def load_index(self) -> bool:
        """Attempts to load existing index"""
        self.update_status(State.LOADING, "Loading index")
        try:
            save_dir = get_index_dir_path()
            vector_store = self.get_vector_store()
            storage_context = StorageContext.from_defaults(
                vector_store=vector_store,
                docstore=SimpleDocumentStore.from_persist_dir(
                    persist_dir=save_dir),
                index_store=SimpleIndexStore.from_persist_dir(
                    persist_dir=save_dir),
            )
            index = load_index_from_storage(storage_context)
            if index is not None:
                self.index = index
                self.update_status(
                    State.READY, "Index loaded and ready to query")
                return True
        except FileNotFoundError:
            print("Existing index not found. Store will not be loaded.")
        except ValueError as e:
            print("Failed to load index; collection likely not found", e)
        self.update_status(State.UNINITIALIZED)
        return False

    async def initialize_or_update(self, source: Source):
        """Initializes or updates a vector store from given source"""

        # If index does not already exist, create it.
        if not self.ready():
            self.update_status(State.CREATING, "Creating index")
            try:
                await self.generate_index(source)
            except Exception as e:
                msg = "Failed to create index"
                print(f"{msg}: {e}", file=sys.stderr)
                self.update_status(State.ERROR, "Failed to create index")
                return

        # This will fetch any _new_ recordings
        # and update the existing index
        self.update_status(State.UPDATING, "Updating index")
        try:
            if source == Source.DAILY:
                await self.index_daily_recordings()
            elif source == Source.UPLOADS:
                await self.generate_upload_transcripts()
            self.index.storage_context.persist(get_index_dir_path())
            self.update_status(State.READY, "Index ready to query")
        except Exception as e:
            print(
                f"failed to update index from source {source} - {e}",
                file=sys.stderr)
            traceback.print_exc()
            self.update_status(State.ERROR, "Failed to update existing index")

    async def generate_index(self, source: Source):
        """Generates a new index from given source"""
        if source == Source.DAILY:
            await self.index_daily_recordings()
        elif source == Source.UPLOADS:
            await self.generate_upload_transcripts()
        self.create_index()

    async def generate_upload_transcripts(self):
        """Generates transcripts from uploaded files"""
        tasks = []

        # Process five files at a time
        sem = asyncio.BoundedSemaphore(5)
        uploaded_file_paths = get_uploaded_file_paths()
        for path in uploaded_file_paths:
            if not path.endswith(".mp4") and not path.endswith(".mov"):
                continue
            tasks.append(asyncio.create_task(
                self.index_uploaded_file(sem, path)))
        # Wait for all processing tasks to finish
        await asyncio.gather(*tasks)

    def create_index(self):
        """Creates a new index
         See: https://gpt-index.readthedocs.io/en/latest/examples/vector_stores/ChromaIndexDemo.html
        """

        # Get all documents from the present transcripts
        documents = SimpleDirectoryReader(
            get_transcripts_dir_path()
        ).load_data()

        vector_store = self.get_vector_store()
        storage_context = StorageContext.from_defaults(
            vector_store=vector_store)
        index = VectorStoreIndex.from_documents(
            documents, storage_context=storage_context
        )
        index.storage_context.persist(persist_dir=get_index_dir_path())
        self.index = index

    async def index_daily_recordings(self):
        """Indexes Daily recordings as per provided room name and max recordings configuration"""
        recordings = fetch_recordings(self.daily_room_name, self.max_videos)

        # Process up to 5 recordings at a time
        sem = asyncio.BoundedSemaphore(5)
        tasks = []
        for recording in recordings:
            tasks.append(asyncio.create_task(
                self.index_daily_recording(sem, recording)))
        # Wait for tasks to complete
        await asyncio.gather(*tasks)

    async def index_daily_recording(self, sem: asyncio.locks.BoundedSemaphore,
                                    recording: Recording):
        """Indexes given Daily recording"""
        async with sem:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.transcribe_and_index_recording, recording)

    async def index_uploaded_file(self, sem: asyncio.locks.BoundedSemaphore, file_path: str):
        """Indexes given uploaded file"""
        async with sem:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.transcribe_and_index_file, file_path)

    def transcribe_and_index_file(self, video_path):
        """Transcribes and indexes locally-saved video recording."""
        file_name = pathlib.Path(video_path).stem

        # Set up transcript file names and paths
        transcript_file_name = f"{file_name}.txt"
        transcripts_dir = get_transcripts_dir_path()
        transcript_file_path = os.path.join(
            transcripts_dir, transcript_file_name)

        # Don't re-transcribe if a transcript for this recording already exists
        if os.path.exists(transcript_file_path):
            os.remove(video_path)
            return

        # If audio for this video does not already exist, extract it.
        audio_path = get_audio_path(video_path)
        if not os.path.exists(audio_path):
            audio_path = extract_audio(video_path)

        # Video no longer needed, remove it.
        os.remove(video_path)

        # Transcribe the generated audio file.
        transcript = self.transcriber.transcribe(None, audio_path)

        # Save the new transcript and _maybe_ index it, if relevant.
        self.save_and_index_transcript(transcript_file_path, transcript)

        # No need to take up disk space with the audio file
        # once we have the transcript saved
        if audio_path:
            os.remove(audio_path)

    def transcribe_and_index_recording(self, recording: Recording):
        """Transcribes and indexes a Daily cloud recording"""

        print("Transcribing and indexing recording:", recording)
        # A safety rail to make sure we only include relevant room name
        # In reality, we specify the room name when querying Daily's REST API
        if self.daily_room_name and self.daily_room_name != recording.room_name:
            return

        file_name = f"{recording.timestamp}_{recording.room_name}_{recording.id}"

        # Set up transcript file names and paths
        transcript_file_name = f"{file_name}.txt"
        transcripts_dir = get_transcripts_dir_path()
        transcript_file_path = os.path.join(
            transcripts_dir, transcript_file_name)

        # Don't re-transcribe if a transcript for this recording already exists
        if os.path.exists(transcript_file_path):
            return

        recording_url = get_access_link(recording.id)
        audio_path = None

        # If the configured transcriber requires a local
        # audio file to be sent, make sure it exists.
        if self.transcriber.requires_local_audio():
            audio_path = get_remote_recording_audio_path(file_name)
            if not os.path.exists(audio_path):
                print("Producing local audio for recording:", recording)
                audio_path = produce_local_audio_from_url(
                    recording_url, file_name)

        try:
            print(f"Transcribing video with {self.transcriber}", recording_url, audio_path)
            transcript = self.transcriber.transcribe(recording_url, audio_path)
        except Exception as e:
            s = str(e)
            if "413" in s:
                # The payload was too large - log and skip
                print(
                    f"Recording {recording_url} was too large; if you want to index it, "
                    f"download the recording and "
                    f"upload in multiple parts")
            else:
                print(f"Failed to transcribe video, moving on to the next {recording_url}: {s}")
            return

        self.save_and_index_transcript(transcript_file_path, transcript)

        # No need to take up disk space once we have the transcript
        if audio_path:
            os.remove(audio_path)

    def save_and_index_transcript(
            self,
            transcript_file_path: str,
            transcript: str):
        """Save the given transcript and index it if the store is ready"""

        # Save transcript to given file path
        with open(transcript_file_path, 'w+', encoding='utf-8') as f:
            f.write(transcript)
            # If the index has been loaded, go ahead and index this transcript
            if self.ready() is True:
                print("Indexing transcript:", transcript_file_path)
                doc = Document(text=transcript)
                self.index.insert(doc)

    def get_vector_store(self):
        """Returns vector store with desired Chroma client, collection, and embed model"""
        chroma_client = chromadb.PersistentClient(path=get_index_dir_path())
        chroma_collection = chroma_client.get_or_create_collection(
            self.collection_name)
        embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-base-en-v1.5")
        vector_store = ChromaVectorStore(
            chroma_collection=chroma_collection, embed_model=embed_model)
        return vector_store

    def ready(self) -> bool:
        """Returns a boolean indicating whether the index is ready to query"""
        return self.index is not None

    def update_status(self, state: State = None, message: str = None):
        """Updates the status of the vector store"""
        # If new state is not specified, keep old state and only update the
        # message
        if state is not None:
            self.status.state = state
        self.status.message = message
