import requests
import argparse
# from dataclasses import dataclass
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from langchain.prompts import ChatPromptTemplate
from datetime import datetime, timedelta
import openai
import os
import json

# Get today's date
today = datetime.today()

# Calculate the date two weeks ago
two_weeks_ago = today - timedelta(weeks=8)

# Format the date as "YYYY-MM-DD"
formatted_date = two_weeks_ago.strftime("%Y-%m-%d")

# Load environment variables. Assumes that project contains .env file with API keys
load_dotenv()
#---- Set OpenAI API key 
# Change environment variable name from "OPENAI_API_KEY" to the name given in 
# your .env file.
openai.api_key = os.environ['OPENAI_API_KEY']
MARKETAUX_API_KEY = os.environ['MARKETAUX_API_KEY']

PROMPT_TEMPLATE = """

Create a GET request (Using this endpoint, with the search query content filled in: 
https://api.marketaux.com/v1/news/all?search=[insert_term_here]&published_after={formatted_date}&language=en&api_token={api_token})
based on the user prompt.

Building a request for financial news search API based on the user prompt. Here are the rules for querying the API:
'Use the search as a basic search tool by entering regular search terms or it has more advanced usage to build search queries:
+ signifies AND operation
| signifies OR operation
- negates a single token
" wraps a number of tokens to signify a phrase for searching
* at the end of a term signifies a prefix query
( and ) signify precedence
To use one of these characters literally, escape it with a preceding backslash (\).
This searches the full body of the text and the title.

Example: "ipo" -nyse (searches for articles which must include the string "ipo" but articles must NOT mention NYSE.)'

---

Return only the URL for the GET request. Here's the user prompt: {question}: 
"""

def execute_request(url):
    raw_response_content = ''
    try:
        raw_response_content = requests.get(url)
        raw_response_content.raise_for_status()  # Raise an exception if the request was unsuccessful
        response_data = raw_response_content.json()  # Convert the response to JSON format
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return None
    results = response_data.get('data')
    return [f"Description: {item['description']}, Snippet: {item['snippet']}" for item in results]
    
def parse_request(data):
    if(data is None or len(data) == 0):
        return None
    return [f"Description: {item.description}, Snippet: {item.snippet}" for item in data]

def query_market(original_query) -> str:
    prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    prompt = prompt_template.format(api_token=MARKETAUX_API_KEY, question=original_query, formatted_date=formatted_date)
    print(prompt)

    model = ChatOpenAI(model="gpt-4o")
    response_text = model.invoke(prompt)
    if response_text.content.startswith("http://") or response_text.content.startswith("https://"):
        return execute_request(response_text.content)
    else:
        return "Invalid URL"
