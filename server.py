from io import BytesIO
import logging
from fastapi import FastAPI, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from langchain.schema import Document
from logic.database_logic.messages import new_chat_message, get_user_conversations, init_conversation
from logic.database_logic.manage_chroma import clear_all_embeddings
from logic.database_logic.types import Conversation
from logic.database_logic.postgres.main import PostgresDatabase
from llama_cloud_services import LlamaParse
from dotenv import load_dotenv

import os

app = FastAPI()

SUBSCRIPTION_PRODUCTS = {
    "RESEARCHER_LITE": 'prod_RYxGo5f1mjy7Q6',
    "RESEARCHER_PRO": 'prod_RYxJXeQ0LKIXLb',
}

# Configure logging
#logging.basicConfig(level=logging.INFO)
# logger = logging.get# logger(__name__)
app = FastAPI()

# Add CORS middleware
origins = [
    "http://localhost:5173",
    "http://localhost:5050",
    "http://localhost:5000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/create-convo/{userId}")
async def create_conversation(file: UploadFile, userId: str, productTypeId: str = Form(...)):
    is_premium_user = productTypeId == SUBSCRIPTION_PRODUCTS["RESEARCHER_PRO"]
    # Read the file contents
    content = await file.read()
    load_dotenv()
    # Initialize LlamaParse client
    parser = LlamaParse(
        api_key=os.environ['LLAMA_CLOUD_API_KEY'],
        verbose=True
    )
    
    try:
        # Create a temporary file name for content tracking
        temp_filename = file.filename or "uploaded_file"
        
        # Parse document using LlamaParse
        raw_documents = await parser.aload_data(
            content,  # Pass the bytes content directly
            extra_info={
                "file_name": temp_filename,
                "content_type": file.content_type
            }
        )
        
        if not raw_documents:
            raise ValueError("No content extracted from document")
            
        # Convert documents to langchain format
        documents = [doc.to_langchain_format() for doc in raw_documents]
            
        # Combine all documents into one if multiple pages were returned
        combined_text = "\n\n".join(doc.page_content for doc in documents)
        
        # Create final document for conversation initialization
        document = Document(
            page_content=combined_text,
            metadata={
                "filename": file.filename,
                "content_type": file.content_type,
                "parsed_by": "llamaparse"
            }
        )
        
        create_convo_response = init_conversation(user_id=userId, document=document, is_premium_user=is_premium_user)
        
        if isinstance(create_convo_response, Conversation):
            # logger.info(f"[/create-convo] Conversation created for user {userId} with conversation ID {create_convo_response.id}")
            return create_convo_response.messages[0].as_json_string()
            
        raise HTTPException(
            status_code=403,
            detail=f"Could not create new conversation. Result: {create_convo_response}"
        )
        
    except Exception as e:
        # logger.error(f"Error processing document: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing document: {str(e)}"
        )
        
@app.get('/conversations/{userId}')
async def get_conversations(userId: str):
    user_conversations = get_user_conversations(userId)
    return user_conversations

@app.get('/quotas/{userId}')
async def get_quotas(userId: str):
    db = PostgresDatabase()
    user_quotas = db.get_quota(userId)
    # logger.info(f"User quotas: {user_quotas}")
    return {"quotas": user_quotas}

@app.post("/new-message/{conversation_id}")
async def new_message(conversation_id: str, body: dict):
    query_text = body.get("queryText")
    dataset_id = body.get("dataSetId")
    user_id = body.get("userId")
    # logger.info(f"Request body {body}")
    new_message_response = new_chat_message(query_text=query_text, user_id=user_id, conversation_id=conversation_id, selected_dataset_id=dataset_id)
    return new_message_response.as_json_string()

@app.get("/clear-chroma-db")
async def create_convo():
    result = clear_all_embeddings()
    if(result):
        return {"message": "Database cleared successfully."}
    return {"message": "Database could not be cleared."}