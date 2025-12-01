import psycopg2
import os

def get_db_connection():
    # Get DATABASE_URL from environment (provided by Render)
    database_url = os.environ.get('DATABASE_URL')
    
    # Parse the database URL (Render provides postgres:// but we need postgresql://)
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    if not database_url:
        # Fallback for local development
        database_url = "postgresql://localhost/event_management"
    
    conn = psycopg2.connect(database_url)
    return conn

def execute_query(query, params=(), fetch=False, fetchall=False):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(query, params)
        
        if fetch:
            result = cursor.fetchone()
            # Convert to dict for compatibility
            if result:
                columns = [desc[0] for desc in cursor.description]
                result = dict(zip(columns, result))
        elif fetchall:
            results = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            result = [dict(zip(columns, row)) for row in results]
        else:
            result = None
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()
    
    return result