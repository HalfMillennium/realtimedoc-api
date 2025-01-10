import psycopg2

class PostgresDatabase:
    def __init__(self, host, port):
        self.conn = psycopg2.connect(
            dbname='realtimedoc',
            user='postgres',
            password='postie',
            host=host,
            port=port
        )
        self.cur = self.conn.cursor()
        self.create_tables()

    def close(self):
        self.cur.close()
        self.conn.close()

    def commit(self):
        self.conn.commit()

    def create_tables(self):
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                conversation_id INTEGER NOT NULL,
                title TEXT NOT NULL
            )
        """)
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                message TEXT NOT NULL,
                author TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                conversation_id INTEGER NOT NULL,
                warning TEXT,
                all_messages TEXT,
                data_store_generation_response TEXT,
                context_used TEXT,
                sources TEXT,
                metadata TEXT
            )
        """)
        self.conn.commit()


    def insert_conversation(self, conversation_data):
        self.cur.execute("""
            INSERT INTO conversations (id, user_id, conversation_id, title)
            VALUES (%s, %s, %s, %s)
        """, (
            conversation_data['id'],
            conversation_data['user_id'],
            conversation_data['conversation_id'],
            conversation_data['title']
        ))
        self.conn.commit()
    
    def delete_conversation(self, conversation_id):
        self.cur.execute(f'DELETE FROM conversations WHERE conversation_id={conversation_id}')
        self.conn.commit()

    def insert_message(self, message_data):
        """
        Inserts a message into the messages table.

        Parameters:
        message_data (dict): A dictionary containing the message details.
            - message (str): The message content.
            - author (str): The author of the message.
            - user_id (int): The ID of the user who sent the message.
            - conversation_id (int): The ID of the conversation the message belongs to.
            - warning (str, optional): Any warning related to the message.
            - all_messages (str, optional): All messages in the conversation.
            - data_store_generation_response (str, optional): Data store generation response.
            - context_used (str, optional): Context used in the message.
            - sources (list, optional): Sources related to the message.
            - metadata (dict, optional): Additional metadata for the message.
        """
        self.cur.execute("""
            INSERT INTO messages (
                message, 
                author,
                user_id,
                timestamp, 
                conversation_id, 
                warning,
                data_store_generation_response, 
                context_used, 
                sources, 
                metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            message_data['message'],
            message_data['author'],
            message_data['user_id'],
            message_data['timestamp'],
            message_data['conversation_id'],
            message_data['warning'],
            message_data['data_store_generation_response'],
            message_data['context_used'],
            message_data['sources'],
            message_data['metadata']
        ))
        self.conn.commit()

    def get_user_conversations(self, user_id):
        self.cur.execute(f'SELECT * FROM conversations WHERE user_id={user_id}')
        data = self.cur.fetchall()
        conversations = []
        for convo in data:
            self.cur.execute(f'SELECT * FROM messages WHERE conversation_id={convo[2]}')
            messages = self.cur.fetchall()
            conversations.append({ 'id': convo[0], 'user_id': convo[1], 'conversation_id': convo[2], 'title': convo[3], 'messages': messages})
        return conversations