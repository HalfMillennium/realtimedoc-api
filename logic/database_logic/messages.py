from langchain_openai import ChatOpenAI
import chromadb
from dotenv import load_dotenv
from langchain.prompts import ChatPromptTemplate
import openai
import os
import uuid
from ..utils import CHROMA_PATH, embed_text
from langchain.schema import Document
from ..dataset_tools.financial_news.get_market_news import query_market
from .types import MessageDBResponse, Conversation
import logging
from .postgres.main import PostgresDatabase
from .manage_chroma import initialize_embedding
from ..dataset_tools.dataset_service import DataSetService
from typing import List
from datetime import datetime
import pytz

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
You are an expert assistant. Answer the user's question by using the following context:

**Document Context - Dataset Name: {dataset_name}**
{dataset_context}

**Conversation History:**
{conversation_history}

**User's Question:**
{question}

**Primary Context**
{context}

Please provide a natural, conversational answer without explicitly stating that you are using different contexts.
"""

POSTGRES_HOST = 'localhost'
POSTGRES_PORT = 5432

def new_chat_message(query_text, user_id, conversation_id, selected_dataset_id: str|None=None) -> MessageDBResponse:
    try:
        db = PostgresDatabase()
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        warning = ""
        # Load the existing embedding
        embeddings_collection = client.get_collection(name=f"{conversation_id}_embeddings")
        if(embeddings_collection is None):
            return MessageDBResponse(message="Embeddings collection not found.", conversation_id=conversation_id, conversation_title="", warning="Embeddings collection not found.")
        query_embedding = embed_text(query_text)
        results = embeddings_collection.query(
            query_embeddings=[query_embedding], # type: ignore
            n_results=10,
            include=["documents", "metadatas", "distances"] # type: ignore
        )

        if len(results) == 0:
            warning = "Unable to find matching results in uploaded document."
        dataset_context = ''
        metadatas = results["metadatas"][0] if results["metadatas"] is not None else []
        documents = results["documents"][0] if results["documents"] is not None else []
        context_text = "{}".format('\n---\n'.join(documents))
        # Get context from dataset, if one is selected
        if selected_dataset_id != None:
            dataset_context = get_dataset_context(selected_dataset_id, query_text)
            logger.info(f"Dataset context: {dataset_context} for dataset {selected_dataset_id}")
        else:
            logger.info("No dataset selected.")
        # Get context from the conversation history
        conversation = db.get_conversation(conversation_id)
        existing_messages = conversation.messages if conversation is not None else []

        prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
        prompt = prompt_template.format(context=context_text, question=query_text, conversation_history=existing_messages, dataset_context=dataset_context, dataset_name=selected_dataset_id)
        logger.info(f'PROMPT: {prompt}')
        model = ChatOpenAI()
        response_text = model.invoke(prompt)

        sources = [metadata.get("source", None) for metadata in metadatas]

        new_bot_message = MessageDBResponse(
            id=str(uuid.uuid4()),
            message=str(response_text.content),
            user_name="RealTimeDoc AI",
            timestamp=datetime.now(pytz.utc).strftime("%m/%d/%Y"),
            conversation_id=conversation_id,
            conversation_title=""
        )

        new_user_message = MessageDBResponse(
            id=str(uuid.uuid4()),
            message=query_text,
            user_name='User',
            timestamp=datetime.now(pytz.utc).strftime("%m/%d/%Y"),
            conversation_id=conversation_id,
            conversation_title="",
            all_messages=[],
            warning=warning,
            metadata={"context_text": context_text, "sources": list(set(sources)), "selected_dataset_id": selected_dataset_id}
        )
        try:
            db.insert_message(message_data=new_user_message)
            db.insert_message(message_data=new_bot_message)
        except Exception as e:
            print(f"Error inserting messages: {str(e)}")
        return new_bot_message
    except Exception as e: 
        return MessageDBResponse(
            message="",
            conversation_id="",
            conversation_title="",
            warning=f"Failed to get new chat message: {e}",
            metadata={}
        )
    
def get_user_conversations(user_id) -> List[Conversation]:
    db = PostgresDatabase()
    return db.get_user_conversations(user_id)

def init_conversation(user_id: str, document: Document, is_premium_user = False) -> Conversation|str:
    db = PostgresDatabase()
    user_quota = db.get_quota(user_id)
    if(not is_premium_user):
        if(user_quota == None):
            initial_admission_date = datetime.now(pytz.utc).strftime("%m/%d/%Y")
            db.insert_quota(user_id=user_id, initial_admission_date=initial_admission_date, daily_counter=1, daily_max=10, total_counter=1)
        else:
            current_date = datetime.now(pytz.utc).date()
            previous_date = datetime.strptime(str(user_quota[1]), "%m/%d/%Y").date()
            '''
            INSERT INTO quotas (
                user_id,
                admission_date,
                daily_counter,
                daily_max,
                total_counter
            ) 
            '''
            if current_date == previous_date and user_quota[2] >= user_quota[3]:
                return f"NO QUOTA: User has reached their daily quota of {user_quota[3]} conversations."
            elif current_date != previous_date:
                db.reset_and_admit_quota(user_id, user_quota[3])
            else:
                db.admit_quota(user_id, user_quota[3])
    init_embedding_response = initialize_embedding(user_id, document, document.metadata['filename'])
    if init_embedding_response:
        logger.info(f"[(func) create_conversation] Embedding initialized for user {user_id} with conversation ID {init_embedding_response.conversation_id}")
        db = PostgresDatabase()
        conversation = Conversation(
            id=init_embedding_response.conversation_id,
            title=init_embedding_response.conversation_title,
            messages=[init_embedding_response]
        )
        db.insert_conversation(conversation, user_id=user_id)
        db.insert_message(message_data=init_embedding_response)
        return conversation
    else:
        raise Exception(f"Could not create new embedding. Result: {init_embedding_response}")
    
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