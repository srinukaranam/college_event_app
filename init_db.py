# init_db.py
import os
import psycopg2

def init_postgresql_tables():
    """Initialize all tables in PostgreSQL"""
    database_url = os.environ.get('DATABASE_URL')
    
    if not database_url:
        print("No DATABASE_URL found. Please set DATABASE_URL environment variable.")
        return
    
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    try:
        conn = psycopg2.connect(database_url, sslmode='require')
        cursor = conn.cursor()
        
        print("Connected to PostgreSQL successfully!")
        
        # Create tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id SERIAL PRIMARY KEY,
                student_id VARCHAR(50) UNIQUE NOT NULL,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(100) NOT NULL,
                department VARCHAR(100),
                year VARCHAR(10),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✓ Created students table")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id SERIAL PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                description TEXT,
                date DATE,
                time TIME,
                venue VARCHAR(100),
                organizer VARCHAR(100),
                capacity INTEGER,
                registered_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✓ Created events table")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS registrations (
                id SERIAL PRIMARY KEY,
                student_id INTEGER REFERENCES students(id) ON DELETE CASCADE,
                event_id INTEGER REFERENCES events(id) ON DELETE CASCADE,
                registration_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                qr_code_path VARCHAR(500),
                checkin_time TIMESTAMP,
                attended BOOLEAN DEFAULT FALSE,
                UNIQUE(student_id, event_id)
            )
        """)
        print("✓ Created registrations table")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS staff (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password VARCHAR(100) NOT NULL,
                name VARCHAR(100) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✓ Created staff table")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password VARCHAR(100) NOT NULL,
                name VARCHAR(100) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✓ Created admins table")
        
        # Insert default admin
        cursor.execute("""
            INSERT INTO admins (username, password, name) 
            VALUES ('admin', 'admin123', 'System Administrator')
            ON CONFLICT (username) DO NOTHING
        """)
        
        # Insert default staff
        cursor.execute("""
            INSERT INTO staff (username, password, name) 
            VALUES ('staff', 'staff123', 'Event Staff')
            ON CONFLICT (username) DO NOTHING
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ All tables created successfully!")
        
    except Exception as e:
        print(f"❌ Error creating tables: {e}")

if __name__ == '__main__':
    init_postgresql_tables()