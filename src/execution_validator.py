import sqlite3
import traceback

def validate_sql_execution(predicted_sql: str, ground_truth_sql: str, db_path: str) -> bool:
    """
    Connects to the SQLite database and compares the execution output.
    Returns True if outputs match (Chosen), False if error/mismatch (Rejected).
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Execute generated SQL
        cursor.execute(predicted_sql)
        predicted_result = set(cursor.fetchall())
        
        # Execute ground truth SQL
        cursor.execute(ground_truth_sql)
        truth_result = set(cursor.fetchall())
        
        conn.close()
        
        # If the outputs match exactly, this is our 'Chosen' SQL
        return predicted_result == truth_result
    except Exception as e:
        # If the SQL crashes (e.g. hallucinates a column), it's 'Rejected'
        return False
