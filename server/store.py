"""This module generates transcripts from the configured Daily domain's recordings
and uses them to create a query-able vector database."""
import asyncio
import dataclasses
import os.path
import sys
import time
from datetime import datetime
from enum import Enum

import chromadb
from llama_index import VectorStoreIndex, SimpleDirectoryReader, StorageContext, \
    ServiceContext, Response, load_index_from_storage, Document
from llama_index.embeddings import HuggingFaceEmbedding
from llama_index.indices.base import BaseIndex
from llama_index.storage.docstore import SimpleDocumentStore
from llama_index.storage.index_store import SimpleIndexStore
from llama_index.vector_stores import ChromaVectorStore

from config import get_transcripts_dir_path, get_index_dir_path
from daily import fetch_recordings, get_access_link, Recording
from media import produce_local_audio_from_url, get_audio_path
from transcription.dg import DeepgramTranscriber
from transcription.whspr import WhisperTranscriber
from transcription.transcriber import Transcriber


class States(str, Enum):
    """Class representing project processing status."""
    UNINITIALIZED = "uninitialized"
    CREATING = "creating"
    UPDATING = "updating"
    LOADING = "loading"
    READY = "ready"
    ERROR = "failed"


@dataclasses.dataclass
class Status:
    state: str
    message: str


class Store:
    status = Status(States.UNINITIALIZED.value, "The store is uninitialized")
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
        self.update_status(States.LOADING, "Loading index")
        if self.load_index():
            self.update_status(States.READY, "Loaded index ready to query")

    async def initialize(self):
        if not self.ready():
            self.update_status(States.CREATING, "Creating index")
            try:
                await self.generate_index()
            except Exception as e:
                msg = "Failed to create index"
                print(f"{msg}: {e}", file=sys.stderr)
                self.update_status(States.ERROR, "Failed to create index")

        else:
            # This will fetch any _new_ recordings
            # and update the existing index
            self.update_status(States.LOADING, "Loading index")
            await self.generate_daily_recording_transcripts()
        self.update_status(States.READY, "Index ready to query")

    async def generate_index(self):
        await self.generate_daily_recording_transcripts()
        self.create_index()

    def load_index(self) -> bool:
        try:
            save_dir = get_index_dir_path()
            vector_store = self.get_vector_store()
            storage_context = StorageContext.from_defaults(
                vector_store=vector_store,
                docstore=SimpleDocumentStore.from_persist_dir(persist_dir=save_dir),
                index_store=SimpleIndexStore.from_persist_dir(persist_dir=save_dir),
            )
            index = load_index_from_storage(storage_context)
            if index is not None:
                self.index = index
                print("Existing index loaded")
                return True
        except FileNotFoundError:
            print("Existing index not found. Database will not be loaded.")
        except ValueError as e:
            print("Failed to load index; collection likely not found", e)
        self.update_status(States.UNINITIALIZED)
        return False

    def create_index(self):
        """
         Docs: https://gpt-index.readthedocs.io/en/latest/examples/vector_stores/ChromaIndexDemo.html
        """
        documents = SimpleDirectoryReader(
            get_transcripts_dir_path()
        ).load_data()

        vector_store = self.get_vector_store(True)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        index = VectorStoreIndex.from_documents(
            documents, storage_context=storage_context
        )
        index.storage_context.persist(persist_dir=get_index_dir_path())
        self.index = index

    def get_vector_store(self, new_collection: bool = False):
        embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-base-en-v1.5")
        chroma_client = chromadb.PersistentClient(path=get_index_dir_path())

        collection_initializer = chroma_client.get_collection
        if new_collection:
            collection_initializer = chroma_client.create_collection
        chroma_collection = collection_initializer(self.collection_name)
        service_context = ServiceContext.from_defaults(embed_model=embed_model)
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection, embed_model=embed_model,
                                         service_context=service_context)

        return vector_store

    async def generate_daily_recording_transcripts(self):
        recordings = fetch_recordings(self.daily_room_name, self.max_videos)
        transcripts_dir = get_transcripts_dir_path()
        sem = asyncio.BoundedSemaphore(5)
        tasks = []
        for recording in recordings:
            tasks.append(asyncio.create_task(self.process_daily_recording(sem, recording, transcripts_dir)))
            print("created task for recording:", recording)
        await asyncio.gather(*tasks)

    async def process_daily_recording(self, sem: asyncio.locks.BoundedSemaphore, recording: Recording,
                                      transcripts_dir: str):
        async with sem:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.transcribe_and_index_recording, recording, transcripts_dir)

    def transcribe_and_index_recording(self, recording: Recording,
                                       transcripts_dir: str):
        # Just a safety rail to make sure we only include relevant room name
        # In reality, we specify the room name when querying Daily's REST API
        if self.daily_room_name and self.daily_room_name != recording.room_name:
            return

        file_name = f"{recording.timestamp}_{recording.room_name}_{recording.id}"
        transcript_file_name = f"{file_name}.txt"
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

    def update_status(self, state: States = None, message: str = None):
        # If new state is not specified, keep old state
        if state is not None:
            self.status.state = state
        self.status.message = message
