import sqlite3
from datetime import datetime

def get_db_connection():
    conn = sqlite3.connect('event_management.db')
    conn.row_factory = sqlite3.Row
    return conn

def execute_query(query, params=(), fetch=False, fetchall=False):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        
        if fetch:
            result = cursor.fetchone()
        elif fetchall:
            result = cursor.fetchall()
        else:
            result = None
            
        conn.commit()
        return result
        
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def init_qr_tables():
    """Initialize database tables for QR functionality"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if checkin_time column exists, if not add it
    try:
        cursor.execute("PRAGMA table_info(registrations)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'checkin_time' not in columns:
            print("Adding checkin_time column to registrations table...")
            cursor.execute("ALTER TABLE registrations ADD COLUMN checkin_time TIMESTAMP")
        
        conn.commit()
        print("QR database tables initialized successfully!")
        
    except Exception as e:
        print(f"Error initializing QR tables: {e}")
        conn.rollback()
    finally:
        conn.close()