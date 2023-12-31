"""This module generates transcripts from the configured Daily domain's recordings
and uses them to create a query-able vector store."""
import asyncio
import dataclasses
import os.path
import pathlib
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor

from enum import Enum

import chromadb
from llama_index import VectorStoreIndex, SimpleDirectoryReader, StorageContext, \
    Response, load_index_from_storage, Document
from llama_index.embeddings import HuggingFaceEmbedding
from llama_index.indices.base import BaseIndex
from llama_index.storage.docstore import SimpleDocumentStore
from llama_index.storage.index_store import SimpleIndexStore
from llama_index.vector_stores import ChromaVectorStore

from config import Config
from daily import fetch_recordings, get_access_link, Recording
from media import (produce_local_audio_from_url, get_audio_path,
                   extract_audio, get_uploaded_file_paths
                   )
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
    config: Config = None
    index: BaseIndex = None
    transcriber: Transcriber = None
    collection_name = "my_first_collection"

    # Daily-related properties
    daily_room_name: str = None
    max_videos: int = None

    executors = []

    def __init__(
            self,
            config: Config = Config(),
            daily_room_name: str = None,
            max_videos: int = None,
            transcriber: Transcriber = None):
        self.config = config
        self.daily_room_name = daily_room_name
        self.max_videos = max_videos
        if not transcriber:
            # Default to local Whisper model if Deepgram API key is not
            # specified
            transcriber = WhisperTranscriber()
            if config.deepgram_api_key:
                transcriber = DeepgramTranscriber(
                    config.deepgram_api_key, config.deepgram_model_name)
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
            save_dir = self.config.index_dir_path
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

        # If an index does not yet exist, create it.
        create_index = not self.ready()
        if create_index:
            self.update_status(State.CREATING, "Creating index")
        else:
            self.update_status(State.UPDATING, "Updating index")

        try:
            # Transcribe videos from given source.
            if source == Source.DAILY:
                await self.process_daily_recordings()
            elif source == Source.UPLOADS:
                await self.process_uploads()

            # If index creation is required, do so.
            if create_index:
                self.create_index()
            self.index.storage_context.persist(self.config.index_dir_path)
            self.update_status(State.READY, "Index ready to query")
        except Exception as e:
            msg = "Failed to create or update index"
            print(f"{msg}: {e}", file=sys.stderr)
            traceback.print_exc()
            self.update_status(State.ERROR,  msg)

    async def process_uploads(self):
        """Generates transcripts from uploaded files and indexes them
        IF an index already exists."""
        uploads = get_uploaded_file_paths(
            self.config.uploads_dir_path)

        uploaded_file_paths = uploads.complete
        tasks = []
        loop = asyncio.get_event_loop()
        # Process five files at a time
        executor = ThreadPoolExecutor(max_workers=5)
        self.executors.append(executor)
        for path in uploaded_file_paths:
            if not path.endswith(".mp4") and not path.endswith(".mov"):
                continue
            task = loop.run_in_executor(
                executor, self.transcribe_and_index_file, path)
            tasks.append(task)

        # Wait for all processing tasks to finish
        await asyncio.gather(*tasks)
        self.executors.remove(executor)

    def create_index(self):
        """Creates a new index
         See: https://gpt-index.readthedocs.io/en/latest/examples/vector_stores/ChromaIndexDemo.html
        """

        # Get all documents from the present transcripts
        documents = SimpleDirectoryReader(
            self.config.transcripts_dir_path
        ).load_data()

        vector_store = self.get_vector_store()
        storage_context = StorageContext.from_defaults(
            vector_store=vector_store)
        index = VectorStoreIndex.from_documents(
            documents, storage_context=storage_context
        )
        self.index = index

    async def process_daily_recordings(self):
        """Generates transcripts from Daily recordings as per provided
        room name and max recordings configuration. Indexes them
        if an index already exists."""

        c = self.config
        recordings = fetch_recordings(
            c.daily_api_key,
            c.daily_api_url,
            self.daily_room_name,
            self.max_videos)

        tasks = []
        loop = asyncio.get_event_loop()
        executor = ThreadPoolExecutor(max_workers=5)
        self.executors.append(executor)
        for recording in recordings:
            task = loop.run_in_executor(
                executor, self.transcribe_and_index_recording, recording)
            tasks.append(task)

        # Wait for tasks to complete
        await asyncio.gather(*tasks)

        self.executors.remove(executor)

    def transcribe_and_index_file(self, video_path):
        """Transcribes and indexes locally-saved video recording."""
        file_name = pathlib.Path(video_path).stem

        transcript_file_path = self.config.get_transcript_file_path(file_name)
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
        transcript_file_path = self.config.get_transcript_file_path(file_name)

        # Don't re-transcribe if a transcript for this recording already exists
        if os.path.exists(transcript_file_path):
            return

        c = self.config
        recording_url = get_access_link(
            c.daily_api_key, recording.id, c.daily_api_url)
        audio_path = None

        # If the configured transcriber requires a local
        # audio file to be sent, make sure it exists.
        if self.transcriber.requires_local_audio():
            audio_path = self.config.get_remote_recording_audio_path(file_name)
            if not os.path.exists(audio_path):
                print("Producing local audio for recording:", recording)
                audio_path = produce_local_audio_from_url(
                    recording_url, file_name)

        try:
            print(
                f"Transcribing video with {self.transcriber}",
                recording_url,
                audio_path)
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
                print(
                    f"Failed to transcribe video, moving on to the next {recording_url}: {s}")
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
        chroma_client = chromadb.PersistentClient(
            path=self.config.index_dir_path)
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

    def destroy(self):
        """Destroy cleans up and shuts down relevant store operations"""
        for executor in self.executors:
            executor.shutdown(kill_workers=True, wait=False)
