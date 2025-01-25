from typing import List
import json
from dataclasses import dataclass
import argparse
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class MessageDBResponse:
    def __init__(self, id: str = '', message: str = '', user_name: str = '', user_id: str = '', timestamp: str = '', conversationId: str = '', conversationTitle: str = '', warning: str = '', allMessages: List[str] = [], data_store_generation_response: str = '', context_used: str = '', sources: List[str] = [], metadata: dict = {}):
        self.id = id
        self.message = message
        self.user_name = user_name
        self.user_id = user_id
        self.conversationId = conversationId
        self.conversationTitle = conversationTitle
        self.allMessages = allMessages
        self.warning = warning
        self.timestamp = timestamp
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
            user_name=data.get('user_name', ''),
            user_id=data.get('user_id', ''),
            timestamp=data.get('timestamp', ''),
            conversationId=data.get('conversationId', ''),
            conversationTitle=data.get('conversationTitle', ''),
            warning=data.get('warning', ''),
            allMessages=data.get('allMessages', []),
            data_store_generation_response=data.get('data_store_generation_response', ''),
            context_used=data.get('context_used', ''),
            sources=data.get('sources', []),
            metadata=data.get('metadata', {})
        )
    
@dataclass
class MarketQueryResult:
    success: bool
    articles: Optional[List[str]] = None
    error_message: Optional[str] = None

@dataclass
class Conversation:
    def __init__(self, id: str, title: str, messages: List[MessageDBResponse], metadata: dict = {}):
        self.id = id
        self.title = title
        self.messages = messages
        self.metadata = metadata