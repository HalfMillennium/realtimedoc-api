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
from ..dataset_tools.financial_news.get_market_news import query_market
from .types import MessageDBResponse, Conversation
import logging
from .postgres.main import PostgresDatabase
from .manage_chroma import get_dataset_context, initialize_embedding
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
Answer the question based on the following context:

{context}

---

Also consider the conversation history: {conversation_history}, and make this response a continuation of that history.

---

Answer the question based on the above context: {question}

Use the content as context, but don't explicity refer to it as context in responses, it should be a natural part of the conversation.
"""

POSTGRES_HOST = 'localhost'
POSTGRES_PORT = 5432

def new_chat_message(query_text, user_id, conversation_id, selected_dataset_id: str|None=None) -> MessageDBResponse:
    try:
        db = PostgresDatabase(host=POSTGRES_HOST, port=POSTGRES_PORT)
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
        conversation = db.get_conversation(conversation_id)
        existing_messages = conversation.messages if conversation is not None else []

        prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
        prompt = prompt_template.format(context=context_text, question=query_text, conversation_history=existing_messages)
        print(f'PROMPT: {prompt}')

        model = ChatOpenAI()
        response_text = model.invoke(prompt)

        sources = [metadata.get("source", None) for metadata in metadatas]

        new_bot_message = MessageDBResponse(
            id=str(uuid.uuid4()),
            message=str(response_text.content),
            user_name="RealTimeDoc AI",
            timestamp=datetime.now(pytz.utc).strftime("%B %d, %I:%M%p"),
            conversation_id=conversation_id,
            conversation_title=""
        )

        new_user_message = MessageDBResponse(
            id=str(uuid.uuid4()),
            message=query_text,
            user_name='User',
            timestamp=datetime.now(pytz.utc).strftime("%B %d, %I:%M%p"),
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
    db = PostgresDatabase(host=POSTGRES_HOST, port=POSTGRES_PORT)
    return db.get_user_conversations(user_id)

def init_conversation(userId: str, document: Document) -> Conversation|str:
    init_embedding_response = initialize_embedding(userId, document, document.metadata['filename'])
    if init_embedding_response:
        logger.info(f"[(func) create_conversation] Embedding initialized for user {userId} with conversation ID {init_embedding_response.conversation_id}")
        db = PostgresDatabase(host=POSTGRES_HOST, port=POSTGRES_PORT)
        conversation = Conversation(
            id=init_embedding_response.conversation_id,
            user_id=userId,
            title=init_embedding_response.conversation_title,
            messages=[init_embedding_response]
        )
        db.insert_conversation(conversation, user_id=userId)
        db.insert_message(init_embedding_response)
        return conversation
    else:
        raise Exception(f"Could not create new embedding. Result: {init_embedding_response}")