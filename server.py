from io import BytesIO
from fastapi import FastAPI, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from langchain.schema import Document
from logic.chroma_database_logic.messages_db import get_new_message, initialize_embedding, clear_all_embeddings, get_embeddings_from_db
import PyPDF2

class Item(BaseModel):
    name: str
    price: float
    is_offer: Optional[bool] = None

app = FastAPI()

# Add CORS middleware
origins = [
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/create-convo/{userId}")
async def create_convo(file: UploadFile, userId: str):
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

    initialize_embedding_response = initialize_embedding(document, userId, file.filename)

    return initialize_embedding_response


@app.post("/new-message/{conversationId}")
async def new_message(conversationId: str, body: dict):
    queryText = body.get("queryText")
    datasetName = body.get("datasetName")
    new_message_response = await get_new_message(query_text=queryText, conversation_id=conversationId, selected_dataset_name=datasetName)
    return new_message_response

@app.get("/get-embeddings")
async def get_embeddings():
    embeddings = get_embeddings_from_db()
    return embeddings

@app.get("/clear-chroma-db")
async def create_convo():
    result = clear_all_embeddings()
    if(result):
        return {"message": "Database cleared successfully."}
    return {"message": "Database could not be cleared."}