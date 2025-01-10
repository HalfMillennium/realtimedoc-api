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
from .manage_chroma import generate_data_store, clear_embeddings, save_messages_to_db, save_conversation_to_user
from ..dataset_tools.financial_news.get_market_news import query_market
from .types import MessageDBResponse, MarketQueryResult
import datetime
import logging
import psycopg2
from ..dataset_tools.dataset_service import DataSetService 
from .postgres.main import PostgresDatabase

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

Use the content as context, but don't explicity refer to it as context in responses, it should be a natural part of the conversation.
"""

DEFAULT_BOT_MESSAGE = "Hi there! I've gone through your document and know it like the back of my hand. Go ahead — ask me anything!"

def get_new_message(query_text, user_id, conversation_id, selected_dataset_id: str|None=None) -> MessageDBResponse:
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
        if selected_dataset_id != None:
            dataset_context = get_dataset_context(selected_dataset_id, query_text)
            if dataset_context != None and dataset_context != "":
                context_text = f"{context_text}\n\n---\n\n{'DATASET CONTEXT: {dataset_context}' if dataset_context is not None else '[]'}"
        else:
            logger.info("No dataset selected.")
        # Get context from the conversation history
        db = PostgresDatabase(host='localhost', port=5432)
        existing_documents = db.get_user_conversations(user_id)

        prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
        prompt = prompt_template.format(context=context_text, question=query_text, conversation_history=existing_documents)
        print(f'PROMPT: {prompt}')

        model = ChatOpenAI()
        response_text = model.invoke(prompt)

        sources = [metadata.get("source", None) for metadata in metadatas]

        new_bot_message = MessageDBResponse(
            message=str(response_text.content),
            author="RealTimeDoc AI",
            conversationId=conversation_id,
            conversationTitle=""
        )

        new_user_message = MessageDBResponse(
            message=query_text,
            author="User",
            conversationId=conversation_id,
            conversationTitle="",
            allMessages=[],
            warning=warning,
            metadata={"context_text": context_text, "sources": list(set(sources)), "selected_dataset_id": selected_dataset_id}
        )

        existing_documents.append(new_user_message.as_json_string())
        existing_documents.append(new_bot_message.as_json_string())
        db.insert_conversation(conversation_data=existing_documents)
        return new_bot_message
    except Exception as e: 
        return MessageDBResponse(
            message="",
            conversationId="",
            conversationTitle="",
            warning=f"Failed to get new chat message: {e}",
            metadata={}
        )

def get_dataset_context(selected_dataset_id: str, query_text: str) -> str|None:
    if selected_dataset_id is not None:
        dataset_service = DataSetService()
        result = None
        if selected_dataset_id == "financial_news":
            result = dataset_service.get_financial_news(query_text)
        elif selected_dataset_id == "us_consumer_spending":
            dataset_service.initialize_spending_db()
            result = dataset_service.get_spending_context(query_text, dataset_id='us_consumer_spending')
        elif selected_dataset_id == "us_national_spending":
            result = dataset_service.get_spending_context(query_text, dataset_id='us_national_spending')
        else:
            logger.error(f"'{selected_dataset_id}' is not a recognized dataset.")
            return None
        return '\n\n'.join(result)
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
