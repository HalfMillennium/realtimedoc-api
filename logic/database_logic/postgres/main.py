import psycopg2
from ..types import Conversation, MessageDBResponse, QuotaResponse
from typing import List
from datetime import datetime
import pytz
import json
import logging

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
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        self.logger.info("Database connection initialized")

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
        self.cur.execute("DELETE FROM conversations WHERE id=%s", (conversation_id,))
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
            message_data.conversation_id,
            message_data.warning,
            message_data.data_store_generation_response,
            message_data.context_used,
            json.dumps(message_data.sources),
            metadata_json
        ))
        self.conn.commit()

    def get_user_conversations(self, user_id) -> List[Conversation]:
        self.cur.execute("SELECT * FROM conversations WHERE user_id=%s", (user_id,))
        data = self.cur.fetchall()
        conversations = []

        for convo in data:
            self.cur.execute(f"SELECT * FROM messages WHERE conversation_id='{convo[0]}'")
            messages = self.cur.fetchall()
            #self.logger.info('messages', messages)
            conversations.append({ 
                'id': convo[0], 
                'user_id': convo[1], 
                'title': convo[2], 
                'messages': messages
            })
        return conversations
    
    def get_conversation(self, conversation_id) -> Conversation|None:
        # Get conversation data
        self.cur.execute("SELECT * FROM conversations WHERE id=%s", (conversation_id,))
        data = self.cur.fetchall()
        
        if not data:
            return None
            
        # Get messages
        self.cur.execute("SELECT * FROM messages WHERE conversation_id=%s", (conversation_id,))
        messages = self.cur.fetchall()
        message_objects = [MessageDBResponse(*message) for message in messages]
        
        conversation_data = data[0]
        return Conversation(
            id=conversation_data[0],
            user_id=conversation_data[1],
            title=conversation_data[2],
            messages=message_objects
        )
    
    def update_quota(self, user_id, last_date, current_count, total_count) -> QuotaResponse:
        self.cur.execute(
            """
            UPDATE quotas
            SET last_date=%s, current_count=%s, total_count=%s
            WHERE user_id=%s
            """,
            (last_date, current_count, total_count, user_id)
        )
        self.conn.commit()
        return QuotaResponse(user_id=user_id, remaining=(10-current_count), message="")

    def set_user_conversation(self, user_id) -> QuotaResponse:
        # Use native datetime in database instead of formatted string
        self.cur.execute("SELECT * FROM quotas WHERE user_id=%s", (user_id,))
        data = self.cur.fetchall()
        
        current_time = datetime.now(pytz.utc)
        
        if not data:
            self.cur.execute("""
                INSERT INTO quotas (
                    user_id,
                    last_date,
                    current_count,
                    total_count
                )
                VALUES (%s, %s, %s, %s)
            """, (
                user_id,
                current_time,
                1,
                1
            ))
            return QuotaResponse(user_id=user_id, remaining=9, message="")

        quota_item = data[0]
        total_count = quota_item[3]
        current_count = quota_item[2]
        last_date = quota_item[1]

        # Reset count if it's a new day
        if last_date.date() < current_time.date():
            current_count = 0
            
        if current_count >= 10:
            return QuotaResponse(user_id=user_id, remaining=0, message="User has maxed out their daily quota.")
            
        # Update with incremented counts
        new_current_count = current_count + 1
        return self.update_quota(
            user_id=user_id,
            last_date=current_time,
            current_count=new_current_count,
            total_count=total_count + 1
        )

    
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