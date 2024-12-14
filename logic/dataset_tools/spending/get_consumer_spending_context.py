from utils import CONSUMER_DATA, CHROMA_PATH, embed_text
from chroma import chromadb
from ...chroma_database_logic.manage_database import generate_data_store

def initialize_consumer_trends_db():
    generate_data_store(path=CONSUMER_DATA, file_type="*.pdf", collectionId="consumer_trends")

def get_consumer_spending_context(query_text, conversation_id) -> str:
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    warning = ""
    collection = client.get_or_create_collection(name=conversation_id)
    query_embedding = embed_text(query_text)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=10,
        include=["documents", "metadatas", "distances"]
    )

    if len(results) != 0:
        documents = results["documents"][0]
    else:
        warning = "Unable to find matching results in uploaded document."

    return {documents: documents, warning: warning}