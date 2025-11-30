import sqlite3
import os

def get_db_connection():
    # Ensure database file exists
    if not os.path.exists('event_management.db'):
        from app import init_database
        init_database()
    
    conn = sqlite3.connect('event_management.db')
    conn.row_factory = sqlite3.Row
    return conn

def execute_query(query, params=(), fetch=False, fetchall=False):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(query, params)
        
        if fetch:
            result = cursor.fetchone()
        elif fetchall:
            result = cursor.fetchall()
        else:
            result = None
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
    
    return result