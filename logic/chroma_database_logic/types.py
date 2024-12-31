from typing import List
import json
from dataclasses import dataclass
import argparse
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class MessageDBResponse:
    def __init__(self, message: str = '', author: str = '', timestamp: str = '', conversationId: str = '', conversationTitle: str = '', warning: str = '', allMessages: List[str] = [], data_store_generation_response: str = '', context_used: str = '', sources: List[str] = [], metadata: dict = {}):
        self.message = message
        self.author = author
        self.conversationId = conversationId
        self.conversationTitle = conversationTitle
        self.allMessages = allMessages
        self.warning = warning
        self.context_used = context_used
        self.sources = sources
        self.data_store_generation_response = data_store_generation_response
        self.metadata = metadata

    def as_json_string(self):
        return json.dumps(self.__dict__)
    
    @staticmethod
    def from_json(json_str: str) -> 'MessageDBResponse':
        data = json.loads(json_str)
        return MessageDBResponse(
            message=data.get('message', ''),
            conversationId=data.get('conversationId', ''),
            conversationTitle=data.get('conversationTitle', ''),
            allMessages=data.get('allMessages', []),
            warning=data.get('warning', ''),
            metadata=data.get('metadata', {})
        )
    
@dataclass
class MarketQueryResult:
    success: bool
    articles: Optional[List[str]] = None
    error_message: Optional[str] = None