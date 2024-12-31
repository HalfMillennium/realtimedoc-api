import chromadb
from langchain_community.document_loaders import DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from dotenv import load_dotenv
import os
import shutil
import logging
import uuid
from typing import List
from ..utils import CHROMA_PATH, embed_text
from .types import MessageDBResponse
from datetime import datetime
import pytz  # For timezone handling
import numpy as np


# Load environment variables. Assumes that project contains .env file with API keys
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Conversation:
    def __init__(self, conversationId: str, messages: List[MessageDBResponse], metadata: dict = {}):
        self.conversationId = conversationId
        self.messages = messages
        self,metadata = metadata

def generate_data_store(collectionId: str, document: Document|None = None, path: str|None = None, file_type: str|None = None) -> str:
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
            embeddings=embeddings,
        )

        logger.info(f"Saved {len(chunks)} embeddings to the database in collection {conversationId}_embeddings.")
        return f"Saved {len(chunks)} embeddings to the database in collection {conversationId}_embeddings."
    except Exception as e:
        logger.error(f"Failed to save embeddings to the database: {e}, attempted {conversationId}")
        return f"Failed to save embeddings to the database: {e}, attempted {conversationId}"
    
def get_user_conversations(userId: str) -> list[Conversation]:
    all_conversations = []
    try:
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        user_collection = client.get_or_create_collection(name=f"{userId}_conversations")
        result = user_collection.get()
        conversations = result.get("documents", [])
        for convo in conversations or []:
            messages_collection = client.get_collection(name=f"{convo}_messages")
            messages = messages_collection.get("documents")
            message_strings = [str(message) for message in messages.items()]
            all_conversations.append(Conversation(conversationId=convo, messages=[MessageDBResponse.from_json(message) for message in message_strings]))
        logger.info(f"Retrieved {len(all_conversations)} conversations for user {userId}.")
        return all_conversations
    except Exception as e:
        logger.error(f"Failed to retrieve user conversations: {e}")
        return []
    
def clear_embeddings():
    if os.path.exists(CHROMA_PATH):
        shutil.rmtree(CHROMA_PATH)
        logger.info(f"Cleared the database at {CHROMA_PATH}.")
        return True
    logger.info(f"Could not find database at {CHROMA_PATH}.")
    return False

def save_messages_to_db(conversationId: str, messages: list[MessageDBResponse]) -> str:
    try:
        # Initialize the persistent client
        client = chromadb.PersistentClient(path=CHROMA_PATH)

        # Load conversation
        messages_collection = client.create_collection(name=f"{conversationId}_messages")

        # Prepare data for insertion
        documents = [message.message for message in messages]
        ids = [str(uuid.uuid4()) for _ in messages]

        # Add data to the messages subcollection
        messages_collection.upsert(
            documents=documents,
            metadatas=[message.metadata if message.metadata else {"placeholder": "value"} for message in messages],
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
        total_uploads = len(metadatas) if metadatas else 0
        
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
        user_collection.upsert(
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
