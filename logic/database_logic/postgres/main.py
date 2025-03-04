import psycopg2
from ..types import Conversation, MessageDBResponse
from typing import List
import json
import logging
import datetime
import pytz
import os

class PostgresDatabase:
    def __init__(self):
        self.conn = psycopg2.connect(
            dbname=os.getenv("POSTGRES_DB", "postgres"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "admin"),
            host=os.getenv("POSTGRES_HOST", "postgres-db"),  # Updated service name
            port=int(os.getenv("POSTGRES_PORT", 5432))
        )
        self.cur = self.conn.cursor()
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

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
        self.cur.execute("""
            CREATE TABLE quotas (
                user_id TEXT PRIMARY KEY,
                admission_date TEXT,
                daily_counter INTEGER,
                daily_max INTEGER,
                total_counter INTEGER
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

    def insert_quota(self, user_id, initial_admission_date, daily_counter, daily_max, total_counter):
        self.logger.info('TIMESTAMP', initial_admission_date)
        self.cur.execute("""
            INSERT INTO quotas (
                user_id,
                admission_date,
                daily_counter,
                daily_max,
                total_counter
            ) 
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s
            );
            """, (user_id, initial_admission_date, daily_counter, daily_max, total_counter))
        self.conn.commit()

    def admit_quota(self, user_id, daily_max):
        current_datetime = datetime.datetime.now(pytz.utc)
        # Should be formatted as MM/DD/YYYY
        formatted_datetime = current_datetime.strftime("%m/%d/%Y")
        self.cur.execute("""
                         UPDATE quotas
                            SET 
                                daily_counter = daily_counter + 1,
                                daily_max = %s,
                                total_counter = total_counter + 1,
                                admission_date = %s
                            WHERE user_id = %s;
            """, (daily_max, formatted_datetime, user_id))
        self.conn.commit()
    
    def get_quota(self, user_id):
        self.cur.execute("""
            SELECT * FROM quotas WHERE user_id='%s'
        """, (user_id,))
        data = self.cur.fetchall()
        self.logger.info(f"Quota data: {data}")
        return data[0] if data and len(data) > 0 else None
    
    def reset_and_admit_quota(self, user_id, daily_max):
        current_datetime = datetime.datetime.now(pytz.utc)
        formatted_datetime = current_datetime.strftime("%m/%d/%Y")
        self.cur.execute("""
                         UPDATE quotas
                            SET 
                                daily_counter = 1,
                                daily_max = %s,
                                total_counter = total_counter + 1,
                                admission_date = %s
                            WHERE user_id = %s;
            """, (daily_max, formatted_datetime, user_id))
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
            self.logger.info(f"Conversation: {convo}")
            self.cur.execute("SELECT * FROM messages WHERE conversation_id=%s", (convo[0],))
            messages = self.cur.fetchall()
            conversations.append({ 
                'id': convo[0], 
                'user_id': convo[1], 
                'title': convo[2], 
                'messages': messages
            })
        return conversations
    
    def get_user_quota(self, user_id):
        self.cur.execute("SELECT * FROM quotas WHERE user_id=%s", (user_id,))
        data = self.cur.fetchall()
        return data[0] if data and len(data) > 0 else None
    
    def get_conversation(self, conversation_id) -> Conversation | None:
        try:
            # Fetch conversation data
            self.cur.execute("SELECT * FROM conversations WHERE id = %s", (conversation_id,))
            data = self.cur.fetchall()
            
            # Check if conversation exists
            if not data:
                return None
            
            # Create conversation object
            conversation = Conversation(*data[0])
            
            # Fetch associated messages
            self.cur.execute("SELECT * FROM messages WHERE conversation_id = %s", (conversation_id,))
            messages = self.cur.fetchall()
            
            # Return a new Conversation object with fetched messages
            return Conversation(
                id=conversation_id,
                title=conversation.title,
                messages=messages # type: ignore
            )
        except Exception as e:
            # Optional: Add error logging or handling
            print(f"Error retrieving conversation: {e}")
            return None
    
if __name__ == '__main__':
    db = PostgresDatabase()
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