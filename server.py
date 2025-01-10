from io import BytesIO
import logging
from fastapi import FastAPI, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from langchain.schema import Document
from logic.database_logic.messages import get_new_message, initialize_embedding, clear_all_embeddings, initialize_conversation_messages
from logic.database_logic.manage_chroma import get_user_conversations
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
    init_embedding_response = initialize_embedding(userId, document, file.filename or "")
    if init_embedding_response:
        logger.info(f"Embedding initialized for user {userId} with conversation ID {init_embedding_response.conversationId}")
        initialize_conversation_messages(userId, init_embedding_response.conversationId)
        return init_embedding_response.as_json_string()

    return {"message": f"Could not create new embedding. Result: {init_embedding_response}"}

@app.get('/conversations/{userId}')
async def get_conversations(userId: str):
    user_conversations = get_user_conversations(userId)
    return user_conversations

@app.post("/new-message/{conversation_id}")
async def new_message(conversation_id: str, body: dict):
    query_text = body.get("queryText")
    dataset_id = body.get("dataSetId")
    user_id = body.get("userId")
    logger.info(f"Request body {body}")
    new_message_response = get_new_message(query_text=query_text, user_id=user_id, conversation_id=conversation_id, selected_dataset_id=dataset_id)
    return new_message_response.as_json_string()

@app.get("/clear-chroma-db")
async def create_convo():
    result = clear_all_embeddings()
    if(result):
        return {"message": "Database cleared successfully."}
    return {"message": "Database could not be cleared."}