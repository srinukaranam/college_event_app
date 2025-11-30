import sqlite3

def init_db():
    # This function is now integrated into app.py
    # Keeping this file for backward compatibility
    pass

if __name__ == '__main__':
    # This allows running models.py directly to initialize database
    from app import init_database
    init_database()
    print("Database initialized successfully!")