import hashlib
import json
from botocore.exceptions import NoCredentialsError
import chromadb
from chromadb import Settings
from langchain_community.document_loaders import DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain_community.vectorstores import Chroma
from dotenv import load_dotenv
import os
import shutil
import logging
import uuid
from ..utils import CHROMA_PATH, HASHES_FILE, embed_text

# Load environment variables. Assumes that project contains .env file with API keys
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_data_store(collectionId: str, document: Document = None, path: str = None, file_type: str = None) -> str:
    documents = [document] if document else load_pdf_documents(path, file_type)
    chunks = split_text(documents)
    return save_embedding_to_db(chunks, collectionId)
    
def load_pdf_documents(path, file_type) -> list[Document]:
    try:
        loader = DirectoryLoader(path, glob=file_type)
        documents = loader.load()
        return documents
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return []
    except IOError as e:
        logger.error(f"Error reading file: {e}")
        return []

def split_text(documents: list[Document]) -> list[Document]:
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=300,
        chunk_overlap=100,
        length_function=len,
        add_start_index=True,
    )
    chunks = text_splitter.split_documents(documents)
    logger.info(f"Split {len(documents)} documents into {len(chunks)} chunks.")

    if chunks:
        document = chunks[10]
        logger.info(document.page_content)
        logger.info(document.metadata)

    return chunks

def get_embeddings_from_db():
    """
    Retrieves all embeddings, along with their associated documents, metadata, and IDs, from the ChromaDB.
    """
    try:
        # Initialize the persistent client
        client = chromadb.PersistentClient(path=CHROMA_PATH)

        # Load the existing collection
        collection = client.get_or_create_collection(name="document_embeddings")
        collection.similarity_search_with_relevance_scores("test", k=10)
        # Fetch all embeddings and associated data
        all_data = collection.get(include=["documents", "metadatas", "embeddings"])

        # Extract and return the data
        documents = all_data.get("documents", [])
        metadatas = all_data.get("metadatas", [])
        ids = all_data.get("ids", [])
        embeddings = all_data.get("embeddings", [])

        logging.info(f"Retrieved {len(embeddings)} embeddings from the database.")
        return {
            "documents": documents,
            "metadatas": metadatas,
            "ids": ids,
            "embeddings": embeddings,
        }

    except Exception as e:
        logging.error(f"Failed to retrieve embeddings from the database: {e}")
        return None


def save_embedding_to_db(chunks: list[Document], collectionId: str) -> str:
    # Load existing hashes
    existing_hashes = load_hashes()
    new_hashes = set()

    # Filter out duplicate chunks
    unique_chunks = []
    for chunk in chunks:
        chunk_hash = compute_hash(chunk.page_content)
        if chunk_hash not in existing_hashes:
            unique_chunks.append(chunk)
            new_hashes.add(chunk_hash)

    if not unique_chunks:
        logger.info("No new unique chunks to add.")
        return

    # Create embeddings for the unique chunks
    embeddings = [embed_text(chunk.page_content) for chunk in unique_chunks]

    # Save the embeddings and metadata to the local database
    try:
        # Initialize the persistent client
        client = chromadb.PersistentClient(path=CHROMA_PATH)

        # Create or load a collection
        collection = client.create_collection(name=collectionId)

        # Prepare data for insertion
        documents = [chunk.page_content for chunk in unique_chunks]
        metadatas = [chunk.metadata for chunk in unique_chunks]
        ids = [str(uuid.uuid4()) for _ in unique_chunks]

        # Add data to the collection
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
            embeddings=embeddings,
        )

        # Update the hashes file
        existing_hashes.update(new_hashes)
        save_hashes(existing_hashes)

        logger.info(f"Saved {len(unique_chunks)} embeddings to the database as collection {collectionId}.")
        return f"Saved {len(unique_chunks)} embeddings to the database as collection {collectionId}."
    except Exception as e:
        logger.error(f"Failed to save embeddings to the database: {e}")
        return f"Failed to save embeddings to the database: {e}"
    
def compute_hash(content: str) -> str:
    return hashlib.md5(content.encode('utf-8')).hexdigest()

def load_hashes() -> set:
    if os.path.exists(HASHES_FILE):
        with open(HASHES_FILE, 'r') as hashes_file:
            return set(json.load(hashes_file))
    return set()

def save_hashes(hashes: set):
    with open(HASHES_FILE, 'w') as hashes_file:
        json.dump(list(hashes), hashes_file)

def clear_embeddings():
    if os.path.exists(CHROMA_PATH):
        shutil.rmtree(CHROMA_PATH)
        logger.info(f"Cleared the database at {CHROMA_PATH}.")
        return True
    logger.info(f"Could not find database at {CHROMA_PATH}.")
    return False

def clear_hashes():
    if os.path.exists(HASHES_FILE):
        os.remove(HASHES_FILE)
        logger.info(f"Cleared the hashes file at {HASHES_FILE}.")
        return True
    logger.info(f"Could not find hashes at {HASHES_FILE}.")
    return False