import chromadb
from langchain_community.document_loaders import DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain_community.vectorstores import Chroma
from dotenv import load_dotenv
import os
import shutil
import logging
import uuid
from ..utils import CHROMA_PATH, embed_text
from datetime import datetime
import pytz  # For consistent timezone handling

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


def save_embedding_to_db(chunks: list[Document], conversationId: str) -> str:

    embeddings = [embed_text(chunk.page_content) for chunk in chunks]

    # Save the embeddings and metadata to the local database
    try:
        # Initialize the persistent client
        client = chromadb.PersistentClient(path=CHROMA_PATH)

        # Create parent + child collection
        embeddings_collection = client.create_collection(name=f"{conversationId}_embeddings")

        # Prepare data for insertion
        documents = [chunk.page_content for chunk in chunks]
        metadatas = [chunk.metadata for chunk in chunks]
        ids = [str(uuid.uuid4()) for _ in chunks]

        # Add data to the collection
        embeddings_collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
            embeddings=embeddings,
        )

        logger.info(f"Saved {len(chunks)} embeddings to the database in collection {conversationId}_embeddings.")
        return f"Saved {len(chunks)} embeddings to the database in collection {conversationId}_embeddings."
    except Exception as e:
        logger.error(f"Failed to save embeddings to the database: {e}, attempted {conversationId}")
        return f"Failed to save embeddings to the database: {e}, attempted {conversationId}"
    
def clear_embeddings():
    if os.path.exists(CHROMA_PATH):
        shutil.rmtree(CHROMA_PATH)
        logger.info(f"Cleared the database at {CHROMA_PATH}.")
        return True
    logger.info(f"Could not find database at {CHROMA_PATH}.")
    return False

class ChatMessage:
    def __init__(self, content: str, author: str, timestamp: str, metadata: dict):
        self.content = content
        self.author = author
        self.timestamp = timestamp
        self.metadata = metadata

def save_messages_to_db(conversationId: str, messages: list[ChatMessage]):
    try:
        # Initialize the persistent client
        client = chromadb.PersistentClient(path=CHROMA_PATH)

        # Load conversation
        messages_collection = client.create_collection(name=f"{conversationId}_messages")

        # Prepare data for insertion
        documents = [message.content for message in messages]
        metadatas = [message.metadata if message.metadata else {"placeholder": "value"} for message in messages]
        ids = [str(uuid.uuid4()) for _ in messages]

        # Add data to the messages subcollection
        messages_collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )

        logger.info(f"Saved {len(messages)} messages to the database in collection {conversationId}_messages.")
        return f"Saved {len(messages)} messages to the database in collection {conversationId}_messages."

    except Exception as e:
        logger.error(f"Failed to save messages to the database: {e}")
        return f"Failed to save messages to the database: {e}"
    
def save_conversation_to_user(conversationId: str, userId: str) -> dict:
    try:
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        user_collection = client.get_or_create_collection(name=f"{userId}_conversations")
        
        # Get current date in UTC
        current_date = datetime.now(pytz.UTC).date().isoformat()
        
        # Get existing conversations
        result = user_collection.get()
        metadatas = result.get("metadatas", [])
        
        # Count today's uploads and find last upload date
        todays_uploads = 0
        last_upload_date = None
        total_uploads = len(metadatas)
        
        if metadatas:
            last_upload_date = metadatas[-1].get("upload_date")
            # Count uploads for today
            todays_uploads = sum(1 for meta in metadatas 
                               if meta.get("upload_date") == current_date)
        
        # Check upload limits
        if todays_uploads >= 10 and last_upload_date == current_date:
            logger.warning(f"User {userId} has reached daily upload limit of 10")
            return {
                "success": False,
                "message": "Daily upload limit reached. Please try again tomorrow.",
                "daily_limit_remaining": "None"
            }
        
        # If we're here, we can proceed with the upload
        user_collection.add(
            documents=[conversationId],
            metadatas=[{
                "conversationId": conversationId,
                "upload_date": current_date,
                "daily_upload_number": todays_uploads + 1,
                "total_upload_number": total_uploads + 1
            }],
            ids=[str(uuid.uuid4())]
        )
        
        logger.info(f"Saved conversation {conversationId} to user {userId}. Upload #{todays_uploads + 1} for today.")
        return {
            "success": True,
            "message": f"Saved conversation. Upload #{todays_uploads + 1} for today.",
            "daily_limit_remaining": 10 - (todays_uploads + 1)
        }
        
    except Exception as e:
        logger.error(f"Failed to save conversation to user: {e}")
        return {
            "success": False,
            "message": f"Failed to save conversation: {e}"
        }
