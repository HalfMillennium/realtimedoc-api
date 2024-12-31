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
from .manage_database import generate_data_store, clear_embeddings, save_messages_to_db, save_conversation_to_user
from ..dataset_tools.financial_news.get_market_news import query_market
from .types import MessageDBResponse, MarketQueryResult
import datetime
import logging

# Load environment variables. Assumes that project contains .env file with API keys
load_dotenv()
#---- Set OpenAI API key 
# Change environment variable name from "OPENAI_API_KEY" to the name given in 
# your .env file.
openai.api_key = os.environ['OPENAI_API_KEY']

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """
Answer the question based on the following context:

{context}

---

Also consider the conversation history: {conversation_history}, and make this response a continuation of that history.

---

Answer the question based on the above context: {question}
"""

DEFAULT_BOT_MESSAGE = "Hi there! I've gone through your document and know it like the back of my hand. Go ahead — ask me anything!"

def get_new_message(query_text, conversation_id, selected_dataset_name=None) -> MessageDBResponse:
    try:
        # Initialize the persistent client
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        warning = ""
        # Load the existing collection
        embeddings_collection = client.get_collection(name=f"{conversation_id}_embeddings")
        if(embeddings_collection is None):
            return MessageDBResponse(message="Embeddings collection not found.", conversationId=conversation_id, conversationTitle="", warning="Embeddings collection not found.")
        query_embedding = embed_text(query_text)
        results = embeddings_collection.query(
            query_embeddings=[query_embedding], # type: ignore
            n_results=10,
            include=["documents", "metadatas", "distances"]
        )

        if len(results) == 0:
            warning = "Unable to find matching results in uploaded document."

        metadatas = results["metadatas"][0] if results["metadatas"] is not None else []
        documents = results["documents"][0] if results["documents"] is not None else []
        context_text = "{}".format('\n---\n'.join(documents))
        # Get context from dataset, if one is selected
        if selected_dataset_name is not None:
            dataset_context = get_dataset_context(selected_dataset_name, query_text)
            if dataset_context != None and dataset_context != "":
                context_text = f"{context_text}\n\n---\n\n{'DATASET CONTEXT: {dataset_context}' if dataset_context is not None else '[]'}"

        # Get context from the conversation history
        conversation_history = client.get_collection(name=f"{conversation_id}_messages")
        all_conversation_messages = conversation_history.get(include=["documents"])

        prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
        prompt = prompt_template.format(context=context_text, question=query_text, conversation_history=all_conversation_messages.items)
        print(prompt)

        model = ChatOpenAI()
        response_text = model.invoke(prompt)

        sources = [metadata.get("source", None) for metadata in metadatas]

        new_message = MessageDBResponse(
            message=str(response_text.content),
            conversationId=conversation_id,
            conversationTitle="",
            allMessages=[],
            warning=warning,
            metadata={"context_text": context_text, "sources": list(set(sources))}
        )
        all_conversation_messages.update(documents=[new_message.as_json_string()])
        return new_message
    except Exception as e: 
        return MessageDBResponse(
            message="",
            conversationId="",
            conversationTitle="",
            warning=f"Failed to get new chat message: {e}",
            metadata={}
        )

def get_dataset_context(selected_dataset_name: str, query_text: str) -> str|None:
    if selected_dataset_name is not None:
        # TODO: Add rest of datasets
        if(selected_dataset_name == "financial_news"):
            result = query_market(query_text)
        return f"'{selected_dataset_name}' is not a recognized dataset."
    return None

def initialize_conversation_messages(userId: str, conversationId: str):
    default_message = MessageDBResponse(
        author="RealTimeDoc AI",
        message=DEFAULT_BOT_MESSAGE,
        timestamp=datetime.datetime.now().strftime("%m/%d/%Y, %I:%M:%S %p"),
        metadata={}
    )
    result = save_messages_to_db(conversationId, [default_message])
    logger.info(result)
    return result

def initialize_embedding(userId: str, document: Document, fileName: str) -> MessageDBResponse:
    warning = ""
    collectionId = str(uuid.uuid4())
    save_conversation_response = save_conversation_to_user(collectionId, userId)
    if(save_conversation_response is None or save_conversation_response['success'] == False):
        return MessageDBResponse(
            message=f"Could not save conversation to user. Result: {save_conversation_response}",
            conversationId="",
            conversationTitle="",
            warning="",
            metadata={}
        )

    data_store_generation_response = generate_data_store(collectionId, document, "*.pdf")
    if data_store_generation_response is None:
        warning = "No message from the data store generation."

    # Create and return the ConversationResponse object
    return MessageDBResponse(
        message=DEFAULT_BOT_MESSAGE,
        conversationId=collectionId,
        conversationTitle=fileName,
        allMessages=[],
        warning=warning,
        data_store_generation_response=data_store_generation_response,
        metadata={"file_name": fileName, "content_type": document.metadata.get("content_type", None), "daily_limit_remaining": save_conversation_response['daily_limit_remaining']}
    )

def clear_all_embeddings():
    clear_db_result = clear_embeddings()
    return clear_db_result
