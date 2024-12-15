import argparse
import shutil
# from dataclasses import dataclass
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_openai import ChatOpenAI
import chromadb
from dotenv import load_dotenv
from langchain.prompts import ChatPromptTemplate
import openai
import os
import uuid
from ..utils import CHROMA_PATH, embed_text
from langchain.schema import Document
from .manage_database import generate_data_store, get_embeddings_from_db, clear_embeddings, clear_hashes
from typing import List, Dict
from ..dataset_tools.financial_news.get_market_news import query_market

class MessageDBResponse:
    def __init__(self, message: str, conversationId: str, conversationTitle: str, warning: str, allMessages: List[str] = None, data_store_generation_response: str = None, context_used: str = None, sources: set = None, metadata: dict = None):
        self.message = message
        self.conversationId = conversationId
        self.conversationTitle = conversationTitle
        self.allMessages = allMessages
        self.warning = warning
        self.context_used = context_used
        self.sources = sources
        self.data_store_generation_response = data_store_generation_response
        self.metadata = metadata

# Load environment variables. Assumes that project contains .env file with API keys
load_dotenv()
#---- Set OpenAI API key 
# Change environment variable name from "OPENAI_API_KEY" to the name given in 
# your .env file.
openai.api_key = os.environ['OPENAI_API_KEY']

PROMPT_TEMPLATE = """
Answer the question based on the following context:

{context}

---

Also consider the conversation history: {conversation_history}, and make this response a continuation of that history.

---

Answer the question based on the above context: {question}
"""

def get_new_message(query_text, conversation_id, selected_dataset_name=None) -> MessageDBResponse:
    # Initialize the persistent client
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    warning = ""
    # Load the existing collection
    collection = client.get_collection(name=conversation_id)
    if(collection is None or collection.id is None):
        return MessageDBResponse(message="Collection not found.", conversationId=conversation_id, conversationTitle="", warning="Collection not found.")
    query_embedding = embed_text(query_text)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=10,
        include=["documents", "metadatas", "distances"]
    )

    if len(results) == 0:
        warning = "Unable to find matching results in uploaded document."

    print('results:', results)

    metadatas = results["metadatas"][0]
    documents = results["documents"][0]

    # Get context from dataset, if one is selected
    if selected_dataset_name is not None:
        dataset_context = get_dataset_context(selected_dataset_name, query_text)
        context_text = "{}".format('\n---\n'.join(documents))
        if dataset_context != None and dataset_context != "":
            context_text = f"{context_text}\n\n---\n\n{'DATASET CONTEXT: ' + dataset_context if dataset_context is not None else '[]'}"

    # TODO: Get context from the conversation history
    conversation_history = "[]"

    prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    prompt = prompt_template.format(context=context_text, question=query_text, conversation_history=conversation_history)
    print(prompt)

    model = ChatOpenAI()
    response_text = model.invoke(prompt)

    sources = [metadata.get("source", None) for metadata in metadatas]

    return { "message": response_text, "collectionId": collection.id, "warning": warning, "context_used": context_text, "sources": set(sources) }

def get_dataset_context(selected_dataset_name: str, query_text: str) -> str:
    if selected_dataset_name is not None:
        # TODO: Add rest of datasets
        if(selected_dataset_name == "financial_news"):
            return query_market(query_text)
        return f"'{selected_dataset_name}' is not a recognized dataset."
    return None

def initialize_embedding(document: Document, userId: str, fileName: str) -> MessageDBResponse:
    # Initialize the persistent client
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    warning = ""
    collectionId = str(uuid.uuid4())

    # TODO: Save collectionId to sqlite/postgres database to associate userIds with collections/conversations
    data_store_generation_response = generate_data_store(collectionId, document, "*.pdf")
    if data_store_generation_response is None:
        warning = "No message from the data store generation."

    # Create and return the ConversationResponse object
    return MessageDBResponse(
        message="Hi there! I've gone through your document and know it like the back of my hand. Go ahead — ask me anything!",
        conversationId=collectionId,
        conversationTitle=fileName,
        allMessages=[],
        warning=warning,
        data_store_generation_response=data_store_generation_response,
        metadata={"file_name": fileName, "content_type": document.metadata.get("content_type", None)}
    )

def get_all_embeddings() -> Dict:
    embeddings = get_embeddings_from_db()
    return embeddings

def clear_all_embeddings():
    clear_db_result = clear_embeddings()
    clear_hashes_result = clear_hashes()
    return clear_db_result and clear_hashes_result
