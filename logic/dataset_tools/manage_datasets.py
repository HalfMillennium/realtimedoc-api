

from ..utils import CONSUMER_SPENDING_DATA, NATIONAL_SPENDING_DATA, CHROMA_PATH, embed_text
import chromadb
from ..chroma_database_logic.manage_database import generate_data_store
from typing import List


def initialize_spending_db():
    # collectionId: str, document: Document = None, path: str = None, file_type: str = None
    init_consumer_spending_result = generate_data_store(collectionId="us_consumer_spending", path=CONSUMER_SPENDING_DATA, file_type="*.pdf")
    init_national_spending_result = generate_data_store(collectionId="us_national_spending", path=NATIONAL_SPENDING_DATA, file_type="*.pdf")
    return {'consumer_spending_result': init_consumer_spending_result, 'national_spending_result': init_national_spending_result}

def get_consumer_spending_context(query_text, conversation_id) -> List[str]:
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    warning = ""
    collection = client.get_or_create_collection(name=conversation_id)
    query_embedding = embed_text(query_text)
    results = collection.query(
        query_embeddings=[query_embedding], # type: ignore
        n_results=10,
        include=["documents", "metadatas", "distances"]
    )

    documents = []
    if len(results) != 0:
        documents = results["documents"][0] if results["documents"] is not None else []

    return documents
