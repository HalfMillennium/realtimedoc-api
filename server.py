from io import BytesIO
import logging
from fastapi import FastAPI, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from langchain.schema import Document
from logic.database_logic.messages import new_chat_message, get_user_conversations, init_conversation
from logic.database_logic.manage_chroma import clear_all_embeddings
from logic.database_logic.types import Conversation
from logic.database_logic.postgres.main import PostgresDatabase
import PyPDF2

app = FastAPI()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
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
async def create_conversation(file: UploadFile, userId: str):
    # Read the file contents
    content = await file.read()

    if file.content_type == "application/pdf":
        pdf_reader = PyPDF2.PdfReader(BytesIO(content))
        page_content = " ".join(page.extract_text() for page in pdf_reader.pages)
    else:
        # Treat as text file (for now)
        page_content = content.decode('utf-8')

    # Convert to langchain.schema.Document
    document = Document(
        page_content=page_content,
        metadata={"filename": file.filename, "content_type": file.content_type}
    )
    create_convo_response = init_conversation(user_id=userId, document=document)
    if isinstance(create_convo_response, Conversation):
        logger.info(f"[/create-convo] Conversation created for user {userId} with conversation ID {create_convo_response.id}")
        #initialize_conversation_messages(userId, init_embedding_response.conversationId)
        return create_convo_response.messages[0].as_json_string()

    return {"message": f"Could not create new conversation. Result: {create_convo_response}"}

@app.get('/conversations/{userId}')
async def get_conversations(userId: str):
    user_conversations = get_user_conversations(userId)
    return user_conversations

@app.get('/quotas/{userId}')
async def get_quotas(userId: str):
    db = PostgresDatabase()
    user_quotas = db.get_quota(userId)
    return user_quotas

@app.post("/new-message/{conversation_id}")
async def new_message(conversation_id: str, body: dict):
    query_text = body.get("queryText")
    dataset_id = body.get("dataSetId")
    user_id = body.get("userId")
    logger.info(f"Request body {body}")
    new_message_response = new_chat_message(query_text=query_text, user_id=user_id, conversation_id=conversation_id, selected_dataset_id=dataset_id)
    return new_message_response.as_json_string()

@app.get("/clear-chroma-db")
async def create_convo():
    result = clear_all_embeddings()
    if(result):
        return {"message": "Database cleared successfully."}
    return {"message": "Database could not be cleared."}