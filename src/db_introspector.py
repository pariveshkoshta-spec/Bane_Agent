import sqlite3
import os

class DatabaseIntrospector:
    def __init__(self, db_path: str):
        self.db_path = db_path
        
    def extract_schemas(self):
        """
        Connects to the SQLite database and automatically extracts
        all CREATE TABLE definitions from the system catalog.
        """
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"Database not found at {self.db_path}")
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Query SQLite's internal system table
        cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL;")
        tables = cursor.fetchall()
        conn.close()
        
        # Create a dictionary of {table_name: create_table_sql}
        schema_dict = {name: sql for name, sql in tables}
        return schema_dict
