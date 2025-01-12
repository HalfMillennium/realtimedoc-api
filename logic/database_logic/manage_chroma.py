import chromadb
from langchain_community.document_loaders import DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from dotenv import load_dotenv
import os
import shutil
import logging
import uuid
from ..utils import CHROMA_PATH, embed_text
from .types import MessageDBResponse, Conversation
from datetime import datetime
import pytz  # For timezone handling
import numpy as np
from ..dataset_tools.dataset_service import DataSetService 
from ..database_logic.postgres.main import PostgresDatabase


DEFAULT_BOT_MESSAGE = "Hi there! I've gone through your document and know it like the back of my hand. Go ahead — ask me anything!"

# Load environment variables. Assumes that project contains .env file with API keys
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    
def clear_embeddings():
    if os.path.exists(CHROMA_PATH):
        shutil.rmtree(CHROMA_PATH)
        logger.info(f"Cleared the database at {CHROMA_PATH}.")
        return True
    logger.info(f"Could not find database at {CHROMA_PATH}.")
    return False

def get_dataset_context(selected_dataset_id: str, query_text: str) -> str|None:
    if selected_dataset_id is not None:
        dataset_service = DataSetService()
        result = None
        if selected_dataset_id == "financial_news":
            result = dataset_service.get_financial_news(query_text)
        elif selected_dataset_id == "us_consumer_spending":
            result = dataset_service.get_spending_context(query_text, dataset_id='us_consumer_spending')
        elif selected_dataset_id == "us_national_spending":
            result = dataset_service.get_spending_context(query_text, dataset_id='us_national_spending')
        else:
            logger.error(f"'{selected_dataset_id}' is not a recognized dataset.")
            return None
        return '\n\n'.join(result)
    return None

def initialize_embedding(userId: str, document: Document, fileName: str) -> MessageDBResponse:
    warning = ""
    collectionId = str(uuid.uuid4())
    '''
    save_conversation_response = save_conversation_to_user(collectionId, userId)
    if(save_conversation_response is None or save_conversation_response['success'] == False):
        return MessageDBResponse(
            message=f"Could not save conversation to user. Result: {save_conversation_response}",
            conversationId="",
            conversationTitle="",
            warning="",
            metadata={}
        )
    '''
    data_store_generation_response = generate_data_store(collectionId, document, "*.pdf")
    if data_store_generation_response is None:
        warning = "No message from the data store generation."

    # Create and return the ConversationResponse object
    return MessageDBResponse(
        id=str(uuid.uuid4()),
        user_name="RealTimeDoc AI",
        message=DEFAULT_BOT_MESSAGE,
        conversationId=collectionId,
        conversationTitle=fileName,
        timestamp=datetime.now(pytz.utc).isoformat(),
        allMessages=[],
        warning=warning,
        data_store_generation_response=data_store_generation_response,
        metadata={"file_name": fileName, "content_type": document.metadata.get("content_type", None), "daily_limit_remaining": 10}
    )

def clear_all_embeddings():
    clear_db_result = clear_embeddings()
    return clear_db_result