from ..utils import CHROMA_PATH, embed_text, CONSUMER_SPENDING_DATA, NATIONAL_SPENDING_DATA
import chromadb
from typing import List
import logging
from .financial_news.get_market_news import query_market
from ..database_logic.manage_chroma import generate_data_store

class DataSetService:
    def __init__(self):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
    def get_spending_context(self, query_text, dataset_id = 'us_consumer_spending') -> List[str]:
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        warning = ""
        collection = None
        try:
            collection = client.get_collection(name=f"{dataset_id}_embeddings")
        except:
            file_path = CONSUMER_SPENDING_DATA if dataset_id == 'us_consumer_spending' else NATIONAL_SPENDING_DATA
            init_spending_db_result = generate_data_store(collectionId=dataset_id, path=file_path, file_type="*.pdf")
            collection = client.get_collection(name=f"{dataset_id}_embeddings")

        query_embedding = embed_text(query_text)
        results = collection.query(
            query_embeddings=[query_embedding], # type: ignore
            n_results=10,
            include=["documents", "metadatas", "distances"] # type: ignore
        )
        documents = []
        if len(results) != 0:
            documents = results["documents"][0] if results["documents"] is not None else []
        return documents
    
    def get_financial_news(self, query_text) -> List[str]:
        results = []
        try:
            results = query_market(query_text)
            return results.articles if results.articles is not None else []
        except Exception as e:
            self.logger.error(f"Error querying market news: {e}")
        return []