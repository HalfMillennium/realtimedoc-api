from ..utils import CONSUMER_SPENDING_DATA, NATIONAL_SPENDING_DATA
from ..database_logic.manage_chroma import generate_data_store
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:        
    init_consumer_spending_result = generate_data_store(collectionId="us_consumer_spending", path=CONSUMER_SPENDING_DATA, file_type="*.pdf")
    init_national_spending_result = generate_data_store(collectionId="us_national_spending", path=NATIONAL_SPENDING_DATA, file_type="*.pdf")
    logger.info(f"CONSUMER SPENDING INIT RESULTS: {init_consumer_spending_result}")
    logger.info(f"NATIONAL SPENDING INIT RESULTS: {init_national_spending_result}")
except Exception as e:
    logger.error(f"Error initializing spending database: {e}")