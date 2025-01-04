from ..utils import CONSUMER_SPENDING_DATA, NATIONAL_SPENDING_DATA, CHROMA_PATH, embed_text
import chromadb
from ..chroma_database_logic.manage_database import generate_data_store
from typing import List
import logging
from .financial_news.get_market_news import query_market

class DataSetService:
    def __init__(self):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        try:
            self.initialize_spending_db()
        except Exception as e:
            self.logger.error(f"Error initializing spending database: {e}")

    def initialize_spending_db(self):
        try:        
            init_consumer_spending_result = generate_data_store(collectionId="us_consumer_spending", path=CONSUMER_SPENDING_DATA, file_type="*.pdf")
            init_national_spending_result = generate_data_store(collectionId="us_national_spending", path=NATIONAL_SPENDING_DATA, file_type="*.pdf")
            self.consumer_spending_result = init_consumer_spending_result
            self.national_spending_result = init_national_spending_result
        except Exception as e:
            self.logger.error(f"Error initializing spending database: {e}")

    def get_spending_context(self, query_text, dataset_id = 'us_consumer_spending') -> List[str]:
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        warning = ""
        collection = client.get_or_create_collection(name=dataset_id)
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
    
    def get_financial_news(self, query_text) -> List[str]:
        results = []
        try:
            results = query_market(query_text)
            return results.articles if results.articles is not None else []
        except Exception as e:
            self.logger.error(f"Error querying market news: {e}")
        return []