"""This module generates transcripts from the configured Daily domain's recordings
and uses them to create a query-able vector database."""
import asyncio
import dataclasses
import os.path
import pathlib
import sys

from enum import Enum

import chromadb
from llama_index import VectorStoreIndex, SimpleDirectoryReader, StorageContext, \
    ServiceContext, Response, load_index_from_storage, Document, PromptTemplate, LLMPredictor
from llama_index.embeddings import HuggingFaceEmbedding
from llama_index.indices.base import BaseIndex
from llama_index.llms import LlamaCPP, HuggingFaceLLM
from llama_index.storage.docstore import SimpleDocumentStore
from llama_index.storage.index_store import SimpleIndexStore
from llama_index.vector_stores import ChromaVectorStore

from config import get_transcripts_dir_path, get_index_dir_path, get_upload_dir_path
from daily import fetch_recordings, get_access_link, Recording
from media import produce_local_audio_from_url, get_audio_path, extract_audio, get_uploaded_file_paths
from transcription.dg import DeepgramTranscriber
from transcription.whspr import WhisperTranscriber
from transcription.transcriber import Transcriber


class State(str, Enum):
    """Class representing project processing status."""
    UNINITIALIZED = "uninitialized"
    CREATING = "creating"
    UPDATING = "updating"
    LOADING = "loading"
    READY = "ready"
    ERROR = "failed"


class Sources(Enum):
    DAILY = "daily"
    UPLOADS = "uploads"


@dataclasses.dataclass
class Status:
    state: str
    message: str


class Store:
    status = Status(State.UNINITIALIZED.value, "The store is uninitialized")
    index: BaseIndex = None
    daily_room_name: str = None
    max_videos: int = None
    transcriber: Transcriber = None
    collection_name = "my_first_collection"

    def __init__(self, daily_room_name: str = None, max_videos: int = None, transcriber: Transcriber = None):
        self.daily_room_name = daily_room_name
        self.max_videos = max_videos
        if not transcriber:
            transcriber = WhisperTranscriber()
            deepgram_api_key = os.getenv("DEEPGRAM_API_KEY")
            if deepgram_api_key:
                transcriber = DeepgramTranscriber()
        self.transcriber = transcriber

    async def initialize_or_update(self, source: Sources):
        print("initialize or update:", source)
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
        if source == Sources.DAILY:
            print("generating recording transcripts from Daily recordings")
            await self.index_daily_recordings()
        elif source == Sources.UPLOADS:
            await self.generate_upload_transcripts()
        self.update_status(State.READY, "Index ready to query")

    async def generate_index(self, source: Sources):
        if source == Sources.DAILY:
            print("generating daily recording transcripts")
            await self.index_daily_recordings()
        elif source == Sources.UPLOADS:
            await self.generate_upload_transcripts()
        self.create_index()

    async def generate_upload_transcripts(self):
        tasks = []
        sem = asyncio.BoundedSemaphore(5)
        uploaded_file_paths = get_uploaded_file_paths()
        for path in uploaded_file_paths:
            if not path.endswith(".mp4") and not path.endswith(".mov"):
                continue
            tasks.append(asyncio.create_task(self.index_uploaded_file(sem, path)))
        await asyncio.gather(*tasks)

    def load_index(self) -> bool:
        self.update_status(State.LOADING, "Loading index")
        try:
            save_dir = get_index_dir_path()
            vector_store = self.get_vector_store()
            storage_context = StorageContext.from_defaults(
                vector_store=vector_store,
                docstore=SimpleDocumentStore.from_persist_dir(persist_dir=save_dir),
                index_store=SimpleIndexStore.from_persist_dir(persist_dir=save_dir),
            )
            index = load_index_from_storage(storage_context)
            print("index:", index)
            if index is not None:
                self.index = index
                print("Existing index loaded")
                self.update_status(State.READY, "Index loaded and ready to query")
                return True
        except FileNotFoundError:
            print("Existing index not found. Store will not be loaded.")
        except ValueError as e:
            print("Failed to load index; collection likely not found", e)
        self.update_status(State.UNINITIALIZED)
        return False

    def create_index(self):
        """
         Docs: https://gpt-index.readthedocs.io/en/latest/examples/vector_stores/ChromaIndexDemo.html
        """
        documents = SimpleDirectoryReader(
            get_transcripts_dir_path()
        ).load_data()

        vector_store = self.get_vector_store()
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        index = VectorStoreIndex.from_documents(
            documents, storage_context=storage_context
        )
        index.storage_context.persist(persist_dir=get_index_dir_path())
        self.index = index

    def get_vector_store(self):
        chroma_client = chromadb.PersistentClient(path=get_index_dir_path())
        chroma_collection = chroma_client.get_or_create_collection(self.collection_name)
        embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-base-en-v1.5")
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection, embed_model=embed_model)

        return vector_store

    def get_service_context(self):
        embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-base-en-v1.5")
        #   llm = self.setup_local_model()
        service_context = ServiceContext.from_defaults(embed_model=embed_model)
        return service_context

    async def index_daily_recordings(self):
        recordings = fetch_recordings(self.daily_room_name, self.max_videos)
        transcripts_dir = get_transcripts_dir_path()
        sem = asyncio.BoundedSemaphore(5)
        tasks = []
        for recording in recordings:
            tasks.append(asyncio.create_task(self.index_daily_recording(sem, recording)))
            print("created task for recording:", recording)
        await asyncio.gather(*tasks)

    async def index_daily_recording(self, sem: asyncio.locks.BoundedSemaphore, recording: Recording):
        async with sem:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.transcribe_and_index_recording, recording)

    async def index_uploaded_file(self, sem: asyncio.locks.BoundedSemaphore, file_path: str):
        async with sem:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.transcribe_and_index_file, file_path)

    def transcribe_and_index_file(self, video_path):
        file_name = pathlib.Path(video_path).stem
        transcript_file_name = f"{file_name}.txt"
        transcripts_dir = get_transcripts_dir_path()
        transcript_file_path = os.path.join(transcripts_dir, transcript_file_name)

        # Don't re-transcribe if a transcript for this recording already exists
        if os.path.exists(transcript_file_path):
            print("removing video 1")
            os.remove(video_path)
            return

        audio_path = get_audio_path(file_name)
        if not os.path.exists(audio_path):
            audio_path = extract_audio(video_path, file_name)

        # Video no longer needed
        print("removing video 2")

        os.remove(video_path)
        transcription = self.transcriber.transcribe(None, audio_path)

        # Save transcript and, if an index already exists, update it
        with open(transcript_file_path, 'w+', encoding='utf-8') as f:
            f.write(transcription)
            if self.ready() is True:
                doc = Document(text=transcription)
                self.index.insert(doc)

        # No need to take up disk space one we have the transcript
        if audio_path:
            os.remove(audio_path)

    def transcribe_and_index_recording(self, recording: Recording):
        # Just a safety rail to make sure we only include relevant room name
        # In reality, we specify the room name when querying Daily's REST API
        if self.daily_room_name and self.daily_room_name != recording.room_name:
            return

        file_name = f"{recording.timestamp}_{recording.room_name}_{recording.id}"

        transcript_file_name = f"{file_name}.txt"
        transcripts_dir = get_transcripts_dir_path()
        transcript_file_path = os.path.join(transcripts_dir, transcript_file_name)

        # Don't re-transcribe if a transcript for this recording already exists
        if os.path.exists(transcript_file_path):
            return

        recording_url = get_access_link(recording.id)
        audio_path = None

        # If the configured transcriber requires a local
        # audio file to be sent, make sure it exists.
        if self.transcriber.requires_local_audio():
            audio_path = get_audio_path(file_name)
            if not os.path.exists(audio_path):
                audio_path = produce_local_audio_from_url(recording_url, file_name)

        transcription = self.transcriber.transcribe(recording_url, audio_path)

        # Save transcript and, if an index already exists, update it
        with open(transcript_file_path, 'w+', encoding='utf-8') as f:
            f.write(transcription)
            if self.ready() is True:
                doc = Document(text=transcription)
                self.index.insert(doc)

        # No need to take up disk space one we have the transcript
        if audio_path:
            os.remove(audio_path)

    def query(self, query: str) -> Response:
        if not self.ready():
            raise Exception("Index not yet initialized. Try again later")
        engine = self.index.as_query_engine()
        response = engine.query(query)
        return response

    def ready(self) -> bool:
        return self.index is not None

    def update_status(self, state: State = None, message: str = None):
        # If new state is not specified, keep old state
        if state is not None:
            self.status.state = state
        self.status.message = message
