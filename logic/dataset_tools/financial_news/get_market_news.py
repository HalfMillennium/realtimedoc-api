import requests
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from langchain.prompts import ChatPromptTemplate
from datetime import datetime, timedelta
from ...chroma_database_logic.types import MarketQueryResult
from typing import List
import openai
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get today's date
today = datetime.today()

# Calculate the date two weeks ago
two_weeks_ago = today - timedelta(weeks=8)

# Format the date as "YYYY-MM-DD"
formatted_date = two_weeks_ago.strftime("%Y-%m-%d")

# Load environment variables. Assumes that project contains .env file with API keys
load_dotenv()

# Set OpenAI API key
openai.api_key = os.environ['OPENAI_API_KEY']
MARKETAUX_API_KEY = os.environ['MARKETAUX_API_KEY']

PROMPT_TEMPLATE = """
Create a GET request (Using this endpoint, with the search query content filled in:
https://api.marketaux.com/v1/news/all?search=[insert_term_here]&published_after={formatted_date}&language=en&api_token={api_token}) based on the user prompt.

Building a request for financial news search API based on the user prompt. Here are the rules for querying the API:
'Use the search as a basic search tool by entering regular search terms or it has more advanced usage to build search queries:
+ signifies AND operation
| signifies OR operation
- negates a single token
" wraps a number of tokens to signify a phrase for searching
* at the end of a term signifies a prefix query
( and ) signify precedence
To use one of these characters literally, escape it with a preceding backslash (\).
This searches the full body of the text and the title.'

Example: "ipo" -nyse (searches for articles which must include the string "ipo" but articles must NOT mention NYSE.)'

---
Return only the URL for the GET request. Here's the user prompt: {question}:
"""

def execute_request(url: str) -> MarketQueryResult:
    try:
        raw_response = requests.get(url)
        raw_response.raise_for_status()
        response_data = raw_response.json()
        results = response_data.get('data', [])
        articles = [
            f"Description: {item['description']}, Snippet: {item['snippet']}" 
            for item in results
        ]
        return MarketQueryResult(success=True, articles=articles)
    except requests.exceptions.RequestException as e:
        logger.error(f"Error: {e}")
        return MarketQueryResult(success=False, error_message=str(e))

def parse_request(data: List[dict]) -> MarketQueryResult:
    if not data:
        return MarketQueryResult(success=False, error_message="No data provided")
    
    try:
        articles = [
            f"Description: {item['description']}, Snippet: {item['snippet']}" 
            for item in data
        ]
        return MarketQueryResult(success=True, articles=articles)
    except (KeyError, TypeError) as e:
        return MarketQueryResult(success=False, error_message=f"Data parsing error: {str(e)}")

def query_market(original_query: str) -> MarketQueryResult:
    prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    prompt = prompt_template.format(
        api_token=MARKETAUX_API_KEY,
        question=original_query,
        formatted_date=formatted_date
    )
    logger.info(prompt)
    
    model = ChatOpenAI(model="gpt-4")
    response = model.invoke(prompt)
    
    if isinstance(response.content, str) and (
        response.content.startswith("http://") or 
        response.content.startswith("https://")
    ):
        return execute_request(response.content)
    else:
        return MarketQueryResult(
            success=False, 
            error_message="Invalid URL returned from model"
        )