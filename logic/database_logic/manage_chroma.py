import chromadb
from langchain_community.document_loaders import DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from dotenv import load_dotenv
import os
import shutil
import uuid
from ..utils import CHROMA_PATH, embed_text
from .types import MessageDBResponse
from datetime import datetime
import pytz
import numpy as np


DEFAULT_BOT_MESSAGE = "Hi there! I've gone through your document and know it like the back of my hand. Go ahead — ask me anything!"

# Load environment variables. Assumes that project contains .env file with API keys
load_dotenv()

# Configure logging
# logging.basicConfig(level=logging.INFO)
# logger = logging.get# logger(__name__)

def generate_data_store(collectionId: str, document: Document|None = None, path: str|None = None, file_type: str|None = None) -> str:
    documents = [document] if document else load_pdf_documents(path, file_type)
    # parse with llamaparse
    chunks = split_text(documents)
    return save_embedding_to_db(chunks, collectionId)
    
def load_pdf_documents(path, file_type) -> list[Document]:
    try:
        loader = DirectoryLoader(path, glob=file_type)
        documents = loader.load()
        return documents
    except FileNotFoundError as e:
        # logger.info('FILE PATH: ' + os.path.abspath(path))
        # logger.error(f"File not found: {e}")
        return []
    except IOError as e:
        # logger.error(f"Error reading file: {e}")
        return []

def split_text(documents: list[Document]) -> list[Document]:
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=300,
        chunk_overlap=100,
        length_function=len,
        add_start_index=True,
    )
    chunks = text_splitter.split_documents(documents)
    # logger.info(f"Split {len(documents)} documents into {len(chunks)} chunks.")
    return chunks

def save_embedding_to_db(chunks: list[Document], conversationId: str) -> str:
    embeddings = [
        np.array(embed_text(chunk.page_content)).tolist() 
        for chunk in chunks
    ]

    # Save the embeddings and metadata to the local database
    try:
        # Initialize the persistent client
        client = chromadb.PersistentClient(path=CHROMA_PATH)

        # Create parent + child collection
        embeddings_collection = client.create_collection(name=f"{conversationId}_embeddings")

        # Prepare data for insertion
        documents = [chunk.page_content for chunk in chunks]
        ids = [str(uuid.uuid4()) for _ in chunks]

        # Add data to the collection
        embeddings_collection.upsert(
            documents=documents,
            metadatas=[chunk.metadata for chunk in chunks],
            ids=ids,
            embeddings=embeddings, # type: ignore
        )

        # logger.info(f"Saved {len(chunks)} embeddings to the database in collection {conversationId}_embeddings.")
        return f"Saved {len(chunks)} embeddings to the database in collection {conversationId}_embeddings."
    except Exception as e:
        # logger.error(f"Failed to save embeddings to the database: {e}, attempted {conversationId}")
        return f"Failed to save embeddings to the database: {e}, attempted {conversationId}"
    
def clear_embeddings():
    if os.path.exists(CHROMA_PATH):
        shutil.rmtree(CHROMA_PATH)
        # logger.info(f"Cleared the database at {CHROMA_PATH}.")
        return True
    # logger.info(f"Could not find database at {CHROMA_PATH}.")
    return False

def initialize_embedding(userId: str, document: Document, fileName: str) -> MessageDBResponse:
    warning = ""
    collection_id = str(uuid.uuid4())
    data_store_generation_response = generate_data_store(collection_id, document, "*.pdf")
    if data_store_generation_response is None:
        warning = "No message from the data store generation."

    # Create and return the ConversationResponse object
    return MessageDBResponse(
        id=str(uuid.uuid4()),
        user_name="RealTimeDoc AI",
        message=DEFAULT_BOT_MESSAGE,
        conversation_id=collection_id,
        conversation_title=fileName,
        timestamp=datetime.now(pytz.utc).strftime("%m/%d/%Y"),
        all_messages=[],
        warning=warning,
        data_store_generation_response=data_store_generation_response,
        metadata={"file_name": fileName, "content_type": document.metadata.get("content_type", None), "daily_limit_remaining": 10}
    )

def clear_all_embeddings():
    clear_db_result = clear_embeddings()
    return clear_db_result