import psycopg2
from ..types import Conversation, MessageDBResponse
from typing import List
import json

class PostgresDatabase:
    def __init__(self, host, port):
        self.conn = psycopg2.connect(
            dbname='realtimedoc',
            user='postgres',
            password='admin',
            host=host,
            port=port
        )
        self.cur = self.conn.cursor()

    def close(self):
        self.cur.close()
        self.conn.close()

    def commit(self):
        self.conn.commit()

    def create_tables(self):
        self.cur.execute("""
            CREATE TABLE conversations (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL
            )
        """)
        self.cur.execute("""
            CREATE TABLE messages (
                id TEXT PRIMARY KEY,
                message TEXT,
                user_id TEXT,
                user_name TEXT,
                timestamp TEXT,
                conversation_id TEXT,
                warning TEXT,
                data_store_generation_response TEXT,
                context_used TEXT,
                sources JSON,
                metadata JSONB
            )
        """)
        self.conn.commit()

    def insert_conversation(self, conversation_data, user_id):
        self.cur.execute("""
            INSERT INTO conversations (id, user_id, title)
            VALUES (%s, %s, %s)
        """, (
            conversation_data.id,
            user_id,
            conversation_data.title
        ))
        self.conn.commit()
    
    def delete_conversation(self, conversation_id):
        self.cur.execute(f"DELETE FROM conversations WHERE id='{conversation_id}'")
        self.conn.commit()

    def insert_message(self, message_data):
        """
        Inserts a message into the messages table.
        """
        # Convert message_data from string to dict if it's not already
        if isinstance(message_data, str):
            message_data = json.loads(message_data)

        metadata_json = json.dumps(message_data.metadata) if message_data.metadata else None
        
        # Clean and prepare other fields
        self.cur.execute("""
            INSERT INTO messages (
                id,
                message, 
                user_id,
                user_name,
                timestamp, 
                conversation_id, 
                warning,
                data_store_generation_response, 
                context_used, 
                sources, 
                metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            message_data.id,
            message_data.message,
            message_data.user_id,
            message_data.user_name,
            message_data.timestamp,
            message_data.conversationId,
            message_data.warning,
            message_data.data_store_generation_response,
            message_data.context_used,
            json.dumps(message_data.sources),
            metadata_json
        ))
        self.conn.commit()

    def get_user_conversations(self, user_id) -> List[Conversation]:
        self.cur.execute(f"SELECT * FROM conversations WHERE user_id='{user_id}'")
        data = self.cur.fetchall()
        conversations = []
        
        for convo in data:
            self.cur.execute(f"SELECT * FROM messages WHERE conversation_id='{convo[0]}'")
            messages = self.cur.fetchall()
            message_objects = [MessageDBResponse(*message) for message in messages]
            conversations.append({ 
                'id': convo[0], 
                'user_id': convo[1], 
                'conversation_id': convo[2], 
                'title': convo[3], 
                'messages': message_objects
            })
        return conversations
    
    def get_conversation(self, conversation_id) -> Conversation|None:
        self.cur.execute(f"SELECT * FROM conversations WHERE id='{conversation_id}'")
        data = self.cur.fetchall()
        conversation_objects = [Conversation(*convo) for convo in data]
        conversation = conversation_objects[0] if len(conversation_objects) > 0 else None
        self.cur.execute(f"SELECT * FROM messages WHERE conversation_id='{conversation_id}'")
        messages = self.cur.fetchall()
        message_objects = [MessageDBResponse(*message) for message in messages]
        if conversation is not None:
            return Conversation(
                id=conversation_id,
                title=conversation.title,
                messages=message_objects
            )
        return None
    
if __name__ == '__main__':
    db = PostgresDatabase(host='localhost', port=5432)
    db.create_tables()

    example_conversation_id = 1
    example_user_id = 1
    conversation_data_1 = {
        'id': 1,
        'conversation_id': example_conversation_id,
        'title': 'Sample Conversation 3'
    }

    db.insert_conversation(conversation_data_1, example_user_id)

    all_conversations = db.get_user_conversations(user_id=1)
    message_data_1 = {
        'id': '1',
        'message': 'Hello, how are you?',
        'user_id': example_user_id,
        'user_name': 'User1',
        'timestamp': None,
        'conversation_id': example_conversation_id,
        'warning': None,
        'data_store_generation_response': None,
        'context_used': None,
        'sources': None,
        'metadata': None
    }

    db.insert_message(message_data_1)

    all_conversations = db.get_user_conversations(user_id=1)
    print('All conversations:', str(all_conversations))