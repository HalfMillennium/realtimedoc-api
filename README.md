RealTimeDoc API
===============

RealTimeDoc API is the backend for the RealTimeDoc application. It is built using Python and leverages modern frameworks and tools to deliver robust functionality for document embedding, querying, and analysis. The API integrates advanced natural language processing and live datasets to provide insightful results.

* * *

Features
--------

*   **FastAPI Server:** A high-performance Python web framework for hosting the backend API.
*   **Document Embeddings:** Uses HuggingFace models to generate embeddings for uploaded documents.
*   **Embeddings Storage:** Stores embeddings efficiently using ChromaDB.
*   **Document Parsing:** Leverages LangChain for advanced document parsing and processing.
*   **Inference:** Utilizes OpenAI's models to perform sophisticated natural language processing tasks.
*   **Live Dataset Integration:**
    *   Integrates data from the U.S. Bureau of Economic Analysis (BEA) for consumer and government spending insights.
    *   Utilizes the Marketaux API for financial market data and news analysis.

* * *

Tech Stack
----------

*   **Python:** The primary programming language for the backend.
*   **FastAPI:** For building and hosting the API server.
*   **HuggingFace:** To generate document embeddings.
*   **ChromaDB:** For storing and managing embeddings.
*   **LangChain:** For parsing and processing document content.
*   **OpenAI:** For inference using advanced NLP models.
*   **BEA Datasets:** Provides consumer and government spending data.
*   **Marketaux API:** Delivers financial market and news datasets.

* * *

Getting Started
---------------

### Prerequisites

*   Python 3.9 or later
*   pip (Python package installer)
*   Access keys for the Marketaux API and OpenAI API

### Installation

1.  **Clone the repository:**
    
        git clone https://github.com/HalfMillennium/realtimedoc-api.git
        cd realtimedoc-api
                    
    
2.  **Create a virtual environment:**
    
        python -m venv venv
        source venv/bin/activate # On Windows: venv\Scripts\activate
                    
    
3.  **Install dependencies:**
    
        pip install -r requirements.txt
    
4.  **Start the server:**
    
        uvicorn main:app --reload
    
5.  **Access the API documentation:** Open your browser and navigate to [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

* * *

Usage
-----

The API exposes endpoints for:

*   Uploading documents
*   Querying stored documents
*   Combining document data with live datasets
*   Retrieving insights from processed data

* * *

Contributing
------------

Contributions are welcome! To contribute:

1.  Fork the repository.
2.  Create a new branch: `git checkout -b feature-name`.
3.  Commit your changes: `git commit -m 'Add feature'`.
4.  Push to the branch: `git push origin feature-name`.
5.  Open a pull request.

* * *

License
-------

This project is licensed under the MIT License. See the `LICENSE` file for details.
