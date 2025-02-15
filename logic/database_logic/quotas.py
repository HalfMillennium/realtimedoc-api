class Quotas:
    def __init__(self, db):
        self.db = db

    def get_quota(self, user_id):
        query = "SELECT * FROM quotas WHERE user_id = %s"
        return self.db.query_one(query, (user_id,))

    def update_quota(self, user_id, quota):
        query = "UPDATE quotas SET quota = %s WHERE user_id = %s"
        return self.db.execute(query, (quota, user_id))

    def create_quota(self, user_id, quota):
        query = "INSERT INTO quotas (user_id, quota) VALUES (%s, %s)"
        return self.db.execute(query, (user_id, quota))