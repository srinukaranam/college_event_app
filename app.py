import csv
import io
import json
import os
import traceback
import psycopg2
import base64
from datetime import datetime
from io import BytesIO
import urllib.parse

from flask import (
    Flask, Response, flash, jsonify, redirect, render_template,
    request, send_file, session, url_for
)

import qrcode
import pandas as pd

# Optional PDF library
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key_here')
app.config['UPLOAD_FOLDER'] = 'static/qrcodes'

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])


from datetime import datetime, date
import datetime as dt

# Add these Jinja2 filters for date handling
# Add Jinja2 filters for date handling
@app.template_filter('format_date')
def format_date_filter(value, format_str='%Y-%m-%d'):
    """Format a date in Jinja2 templates"""
    if isinstance(value, (date, datetime)):
        return value.strftime(format_str)
    elif isinstance(value, str):
        try:
            # Try to parse string date
            date_obj = datetime.strptime(value, '%Y-%m-%d')
            return date_obj.strftime(format_str)
        except:
            return value
    return str(value)

@app.template_filter('format_datetime')
def format_datetime_filter(value, format_str='%Y-%m-%d %H:%M:%S'):
    """Format a datetime in Jinja2 templates"""
    if isinstance(value, (datetime, date)):
        return value.strftime(format_str)
    elif isinstance(value, str):
        try:
            # Try to parse string datetime
            if ' ' in value:
                dt_obj = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
            else:
                dt_obj = datetime.strptime(value, '%Y-%m-%d')
            return dt_obj.strftime(format_str)
        except:
            return value
    return str(value)

@app.template_filter('get_day')
def get_day_filter(value):
    """Get day from date"""
    if isinstance(value, (date, datetime)):
        return value.strftime('%d')
    elif isinstance(value, str):
        try:
            date_obj = datetime.strptime(value, '%Y-%m-%d').date()
            return date_obj.strftime('%d')
        except:
            return '??'
    return '??'

@app.template_filter('get_month_year')
def get_month_year_filter(value):
    """Get month/year from date"""
    if isinstance(value, (date, datetime)):
        return value.strftime('%m/%Y')
    elif isinstance(value, str):
        try:
            date_obj = datetime.strptime(value, '%Y-%m-%d').date()
            return date_obj.strftime('%m/%Y')
        except:
            return '??/????'
    return '??/????'

# Add datetime to Jinja2 context
@app.context_processor
def inject_datetime():
    return {'datetime': datetime}

# -----------------------
# Database Configuration with SSL for Render
# -----------------------
def get_db_connection():
    """Get PostgreSQL database connection from Render"""
    database_url = os.environ.get('DATABASE_URL')
    
    if not database_url:
        print("WARNING: DATABASE_URL not set. Using fallback.")
        # Fallback for local development
        database_url = "postgresql://localhost/event_management"
    
    # Fix URL format for SQLAlchemy/Render
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    try:
        # Add SSL requirement for Render PostgreSQL
        conn = psycopg2.connect(database_url, sslmode='require')
        print("✅ Connected to PostgreSQL successfully")
        return conn
    except Exception as e:
        print(f"❌ Error connecting to PostgreSQL: {e}")
        # Try without SSL for local development
        try:
            conn = psycopg2.connect(database_url)
            print("✅ Connected without SSL (local)")
            return conn
        except Exception as e2:
            print(f"❌ Connection failed: {e2}")
            return None

def execute_query(query, params=(), fetch=False, fetchall=False):
    """Execute query with proper error handling"""
    conn = get_db_connection()
    if conn is None:
        print("❌ Database connection failed")
        return None
    
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        
        if fetch:
            result = cursor.fetchone()
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
        return result
        
    except Exception as e:
        print(f"❌ Database query error: {e}")
        print(f"Query: {query}")
        print(f"Params: {params}")
        if conn:
            conn.rollback()
        return None
    finally:
        if conn:
            conn.close()

# -----------------------
# Check and Initialize Database
# -----------------------
def check_and_init_database():
    """Check if database tables exist, create if not"""
    try:
        print("🔍 Checking database tables...")
        
        # Test connection first
        conn = get_db_connection()
        if conn is None:
            print("❌ Cannot connect to database")
            return False
        
        cursor = conn.cursor()
        
        # Check if students table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'students'
            )
        """)
        tables_exist = cursor.fetchone()[0]
        
        if not tables_exist:
            print("📦 Tables don't exist. Creating tables...")
            
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
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS registrations (
                    id SERIAL PRIMARY KEY,
                    student_id INTEGER REFERENCES students(id) ON DELETE CASCADE,
                    event_id INTEGER REFERENCES events(id) ON DELETE CASCADE,
                    registration_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    qr_code_path TEXT,
                    checkin_time TIMESTAMP,
                    attended BOOLEAN DEFAULT FALSE,
                    UNIQUE(student_id, event_id)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS staff (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    password VARCHAR(100) NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS admins (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    password VARCHAR(100) NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
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
            print("✅ All tables created successfully!")
        else:
            print("✅ Database tables already exist")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error checking database: {e}")
        print(traceback.format_exc())
        return False

# Initialize database when app starts
print("🚀 Starting application...")
with app.app_context():
    if check_and_init_database():
        print("✅ Database initialization complete")
    else:
        print("❌ Database initialization failed")

# -----------------------
# Debug route to check database status
# -----------------------
@app.route('/debug/db')
def debug_db():
    """Debug endpoint to check database status"""
    try:
        database_url = os.environ.get('DATABASE_URL', 'Not set')
        masked_url = database_url
        if database_url != 'Not set':
            # Mask password in URL for security
            if '@' in database_url:
                parts = database_url.split('@')
                user_part = parts[0]
                if ':' in user_part:
                    user_pass = user_part.split(':')
                    if len(user_pass) > 2:
                        masked_url = f"{user_pass[0]}:****@{parts[1]}"
        
        # Check tables
        tables = {}
        try:
            tables['students'] = execute_query("SELECT COUNT(*) as count FROM students", fetch=True)
            tables['events'] = execute_query("SELECT COUNT(*) as count FROM events", fetch=True)
            tables['registrations'] = execute_query("SELECT COUNT(*) as count FROM registrations", fetch=True)
            tables['staff'] = execute_query("SELECT COUNT(*) as count FROM staff", fetch=True)
            tables['admins'] = execute_query("SELECT COUNT(*) as count FROM admins", fetch=True)
        except Exception as e:
            tables['error'] = str(e)
        
        # Get recent data
        recent_students = execute_query("SELECT student_id, name FROM students ORDER BY id DESC LIMIT 5", fetchall=True) or []
        recent_events = execute_query("SELECT title, date FROM events ORDER BY id DESC LIMIT 5", fetchall=True) or []
        
        return render_template('debug_db.html',
                             database_url=masked_url,
                             tables=tables,
                             recent_students=recent_students,
                             recent_events=recent_events)
    except Exception as e:
        return f"<h1>Error</h1><pre>{str(e)}</pre><pre>{traceback.format_exc()}</pre>"

# -----------------------
# Basic pages & auth flows
# -----------------------
@app.route('/')
def index():
    return render_template('index.html')

# Student registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        student_id = request.form['student_id']
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        department = request.form['department']
        year = request.form['year']
        
        # Check if student already exists
        existing_student = execute_query(
            "SELECT * FROM students WHERE student_id = %s OR email = %s", 
            (student_id, email), 
            fetch=True
        )
        
        if existing_student:
            flash('Student ID or Email already exists!', 'error')
            return redirect(url_for('register'))
        
        # Insert new student
        result = execute_query(
            "INSERT INTO students (student_id, name, email, password, department, year) VALUES (%s, %s, %s, %s, %s, %s)",
            (student_id, name, email, password, department, year)
        )
        
        if result is None:
            flash('Database error! Please try again.', 'error')
            return redirect(url_for('register'))
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

# Student login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        student = execute_query(
            "SELECT * FROM students WHERE email = %s AND password = %s", 
            (email, password), 
            fetch=True
        )
        
        if student:
            session['student_id'] = student['id']
            session['student_name'] = student['name']
            flash(f'Welcome back, {student["name"]}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password!', 'error')
    
    return render_template('login.html')

# Student dashboard
@app.route('/dashboard')
def dashboard():
    if 'student_id' not in session:
        return redirect(url_for('login'))
    
    # Get upcoming events
    today = datetime.now().strftime('%Y-%m-%d')
    upcoming_events = execute_query(
        "SELECT * FROM events WHERE date >= %s ORDER BY date, time", 
        (today,), 
        fetchall=True
    ) or []
    
    # Get student's registrations
    registrations = execute_query(
        """SELECT e.*, r.registration_time, r.qr_code_path 
           FROM events e 
           JOIN registrations r ON e.id = r.event_id 
           WHERE r.student_id = %s""",
        (session['student_id'],),
        fetchall=True
    ) or []
    
    return render_template('dashboard.html', 
                         student_name=session['student_name'],
                         upcoming_events=upcoming_events,
                         registrations=registrations)

# Events page
@app.route('/events')
def events():
    if 'student_id' not in session:
        return redirect(url_for('login'))
    
    # Get all upcoming events
    today = datetime.now().strftime('%Y-%m-%d')
    events_list = execute_query(
        "SELECT * FROM events WHERE date >= %s ORDER BY date, time", 
        (today,), 
        fetchall=True
    ) or []
    
    return render_template('events.html', events=events_list)

# Event details and registration
@app.route('/event/<int:event_id>')
def event_details(event_id):
    if 'student_id' not in session:
        return redirect(url_for('login'))
    
    event = execute_query(
        "SELECT * FROM events WHERE id = %s", 
        (event_id,), 
        fetch=True
    )
    
    if not event:
        flash('Event not found!', 'error')
        return redirect(url_for('events'))
    
    # Check if student is already registered
    registration = execute_query(
        "SELECT * FROM registrations WHERE student_id = %s AND event_id = %s", 
        (session['student_id'], event_id), 
        fetch=True
    )
    
    return render_template('event_details.html', event=event, registration=registration)

# Register for event - FIXED: Uses base64 for QR codes
@app.route('/register_event/<int:event_id>')
def register_event(event_id):
    if 'student_id' not in session:
        return redirect(url_for('login'))
    
    # Check if event exists and has capacity
    event = execute_query(
        "SELECT * FROM events WHERE id = %s", 
        (event_id,), 
        fetch=True
    )
    
    if not event:
        flash('Event not found!', 'error')
        return redirect(url_for('events'))
    
    if event['registered_count'] >= event['capacity']:
        flash('Event is full!', 'error')
        return redirect(url_for('event_details', event_id=event_id))
    
    # Check if already registered
    existing_registration = execute_query(
        "SELECT * FROM registrations WHERE student_id = %s AND event_id = %s", 
        (session['student_id'], event_id), 
        fetch=True
    )
    
    if existing_registration:
        flash('You are already registered for this event!', 'error')
        return redirect(url_for('event_details', event_id=event_id))
    
    # Get student details for QR code
    student = execute_query(
        "SELECT * FROM students WHERE id = %s", 
        (session['student_id'],), 
        fetch=True
    )
    
    if not student:
        flash('Student not found!', 'error')
        return redirect(url_for('events'))
    
    try:
        # Generate QR code data
        qr_data = f"""
Event: {event['title']}
Student: {student['name']}
Student ID: {student['student_id']}
Event Date: {event['date']}
Event Time: {event['time']}
Venue: {event['venue']}
Registration ID: {student['student_id']}_{event_id}
        """.strip()
        
        # Create QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        # Create QR code image
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        # Save QR code to BytesIO (in memory)
        buffer = BytesIO()
        qr_img.save(buffer, format="PNG")
        buffer.seek(0)
        
        # Convert to base64 for storage
        qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        # Store base64 in database
        qr_web_path = f"data:image/png;base64,{qr_base64}"
        
        # Register for event
        execute_query(
            "INSERT INTO registrations (student_id, event_id, qr_code_path) VALUES (%s, %s, %s)",
            (session['student_id'], event_id, qr_web_path)
        )
        
        # Update event registration count
        execute_query(
            "UPDATE events SET registered_count = registered_count + 1 WHERE id = %s",
            (event_id,)
        )
        
        flash('Successfully registered for the event! QR code generated.', 'success')
        return redirect(url_for('event_details', event_id=event_id))
        
    except Exception as e:
        print(f"Error in register_event: {str(e)}")
        print(traceback.format_exc())
        flash('Error generating QR code. Please try again.', 'error')
        return redirect(url_for('event_details', event_id=event_id))

# My registrations
@app.route('/my_registrations')
def my_registrations():
    if 'student_id' not in session:
        return redirect(url_for('login'))
    
    registrations = execute_query(
        """SELECT e.*, r.registration_time, r.qr_code_path, r.attended 
           FROM events e 
           JOIN registrations r ON e.id = r.event_id 
           WHERE r.student_id = %s 
           ORDER BY e.date, e.time""",
        (session['student_id'],),
        fetchall=True
    ) or []
    
    return render_template('my_registrations.html', registrations=registrations)

# Staff login
@app.route('/staff/login', methods=['GET', 'POST'])
def staff_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        staff = execute_query(
            "SELECT * FROM staff WHERE username = %s AND password = %s", 
            (username, password), 
            fetch=True
        )
        
        if staff:
            session['staff_id'] = staff['id']
            session['staff_name'] = staff['name']
            flash(f'Welcome, {staff["name"]}!', 'success')
            return redirect(url_for('staff_dashboard'))
        else:
            flash('Invalid username or password!', 'error')
    
    return render_template('staff_login.html')

# Staff dashboard
@app.route('/staff/dashboard')
def staff_dashboard():
    if 'staff_id' not in session:
        return redirect(url_for('staff_login'))
    return render_template('staff_dashboard.html')

# Staff QR verification - FIXED: Handles base64 QR codes
@app.route('/staff/verify', methods=['POST'])
def staff_verify():
    if 'staff_id' not in session:
        return jsonify({'success': False, 'message': 'Staff access required'})
    
    qr_data = request.json.get('qr_data')
    
    if not qr_data:
        return jsonify({'success': False, 'message': 'No QR data provided'})
    
    try:
        # Parse QR data
        lines = qr_data.strip().split('\n')
        qr_dict = {}
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                qr_dict[key.strip()] = value.strip()
        
        event_title = qr_dict.get('Event', '')
        student_id_str = qr_dict.get('Student ID', '')
        
        if not event_title or not student_id_str:
            return jsonify({'success': False, 'message': 'Invalid QR code format'})
        
        # Get student by student_id
        student = execute_query(
            "SELECT * FROM students WHERE student_id = %s", 
            (student_id_str,), 
            fetch=True
        )
        
        # Get event by title
        event = execute_query(
            "SELECT * FROM events WHERE title = %s", 
            (event_title,), 
            fetch=True
        )
        
        if not student:
            return jsonify({'success': False, 'message': 'Student not found'})
        
        if not event:
            return jsonify({'success': False, 'message': 'Event not found'})
        
        # Check if student is registered for this event
        registration = execute_query(
            "SELECT * FROM registrations WHERE student_id = %s AND event_id = %s", 
            (student['id'], event['id']), 
            fetch=True
        )
        
        if not registration:
            return jsonify({'success': False, 'message': 'Student not registered for this event'})
        
        # Check if already attended
        if registration['attended']:
            return jsonify({
                'success': False, 
                'message': f"Student {student['name']} has already checked in for this event"
            })
        
        # Mark as attended with timestamp
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        execute_query(
            "UPDATE registrations SET attended = TRUE, checkin_time = %s WHERE student_id = %s AND event_id = %s",
            (current_time, student['id'], event['id'])
        )
        
        return jsonify({
            'success': True,
            'student': {
                'name': student['name'],
                'student_id': student['student_id'],
                'department': student['department'],
                'year': student['year']
            },
            'event': {
                'id': event['id'],
                'title': event['title'],
                'date': event['date'],
                'time': event['time'],
                'venue': event['venue'],
                'organizer': event['organizer']
            },
            'checkin_time': current_time
        })
        
    except Exception as e:
        print(f"Staff verification error: {str(e)}")
        return jsonify({'success': False, 'message': f'Error processing QR code: {str(e)}'})

# Staff logout
@app.route('/staff/logout')
def staff_logout():
    session.pop('staff_id', None)
    session.pop('staff_name', None)
    flash('Staff logged out successfully!', 'success')
    return redirect(url_for('staff_login'))

# Staff scan page
@app.route('/staff_scan')
def staff_scan():
    if 'staff_id' not in session:
        flash('Access denied. Staff access required.', 'error')
        return redirect(url_for('staff_login'))
    return render_template('staff_scan.html')

# Staff verification page
@app.route('/staff_verify_page', methods=['GET', 'POST'])
def staff_verify_page():
    if 'staff_id' not in session:
        flash('Access denied. Staff access required.', 'error')
        return redirect(url_for('staff_login'))
        
    if request.method == 'POST':
        qr_data = request.form.get('qr_data')
        
        if not qr_data:
            return render_template('staff_verify.html', 
                                 success=False, 
                                 message='No QR code data provided')
        
        try:
            # Parse QR data
            lines = qr_data.strip().split('\n')
            qr_dict = {}
            for line in lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    qr_dict[key.strip()] = value.strip()
            
            # Extract information from QR data
            event_title = qr_dict.get('Event', '')
            student_id_str = qr_dict.get('Student ID', '')
            
            if not event_title or not student_id_str:
                return render_template('staff_verify.html', 
                                     success=False, 
                                     message='Invalid QR code format')
            
            # Get student by student_id
            student = execute_query(
                "SELECT * FROM students WHERE student_id = %s", 
                (student_id_str,), 
                fetch=True
            )
            
            # Get event by title
            event = execute_query(
                "SELECT * FROM events WHERE title = %s", 
                (event_title,), 
                fetch=True
            )
            
            if student and event:
                # Check if student is registered for this event
                registration = execute_query(
                    "SELECT * FROM registrations WHERE student_id = %s AND event_id = %s", 
                    (student['id'], event['id']), 
                    fetch=True
                )
                
                if registration:
                    # Check if already attended
                    if registration['attended']:
                        return render_template('staff_verify.html',
                                             success=False,
                                             message=f"Student {student['name']} has already checked in for this event")
                    
                    # Mark as attended with timestamp
                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    execute_query(
                        "UPDATE registrations SET attended = TRUE, checkin_time = %s WHERE student_id = %s AND event_id = %s",
                        (current_time, student['id'], event['id'])
                    )
                    
                    return render_template('staff_verify.html',
                                         success=True,
                                         student=student,
                                         event=event,
                                         checkin_time=current_time)
                else:
                    return render_template('staff_verify.html', 
                                         success=False, 
                                         message='Student not registered for this event')
            else:
                return render_template('staff_verify.html', 
                                     success=False, 
                                     message='Invalid student or event information')
        
        except Exception as e:
            print(f"Verification error: {str(e)}")
            return render_template('staff_verify.html', 
                                 success=False, 
                                 message=f'Error processing QR code: {str(e)}')
    
    # GET request - show verification history or recent scans
    recent_verifications = execute_query(
        """SELECT s.name, s.student_id, e.title, r.checkin_time 
           FROM registrations r 
           JOIN students s ON r.student_id = s.id 
           JOIN events e ON r.event_id = e.id 
           WHERE r.attended = TRUE 
           ORDER BY r.checkin_time DESC 
           LIMIT 10""",
        fetchall=True
    ) or []
    
    return render_template('staff_verify.html', recent_verifications=recent_verifications)

# Admin login
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        admin = execute_query("SELECT * FROM admins WHERE username = %s AND password = %s", (username, password), fetch=True)
        if admin:
            session['admin_id'] = admin['id']
            session['admin_name'] = admin['name']
            flash(f'Welcome, {admin["name"]}!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid username or password!', 'error')
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))

    total_events = execute_query("SELECT COUNT(*) as count FROM events", fetch=True)
    total_students = execute_query("SELECT COUNT(*) as count FROM students", fetch=True)
    total_registrations = execute_query("SELECT COUNT(*) as count FROM registrations", fetch=True)

    recent_events = execute_query("SELECT * FROM events ORDER BY created_at DESC LIMIT 5", fetchall=True) or []
    
    # Format dates for display
    for event in recent_events:
        if event.get('date'):
            event['date_str'] = event['date'].strftime('%Y-%m-%d')
            event['date_day'] = event['date'].strftime('%d')
            event['date_month'] = event['date'].strftime('%m')
            event['date_year'] = event['date'].strftime('%Y')

    recent_verifications = execute_query(
        """SELECT s.name as student_name, s.student_id, e.title as event_title, r.checkin_time
           FROM registrations r
           JOIN students s ON r.student_id = s.id
           JOIN events e ON r.event_id = e.id
           WHERE r.attended = TRUE
           ORDER BY r.checkin_time DESC
           LIMIT 10""",
        fetchall=True
    ) or []

    return render_template('admin_dashboard.html',
                           admin_name=session.get('admin_name'),
                           total_events=total_events['count'] if total_events else 0,
                           total_students=total_students['count'] if total_students else 0,
                           total_registrations=total_registrations['count'] if total_registrations else 0,
                           recent_events=recent_events,
                           recent_verifications=recent_verifications)

# Admin events list
@app.route('/admin/events')
def admin_events():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    events = execute_query("SELECT * FROM events ORDER BY date, time", fetchall=True) or []
    return render_template('admin_events.html', events=events)

# Create Event
@app.route('/admin/create_event', methods=['GET', 'POST'])
def create_event():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        date = request.form['date']
        time = request.form['time']
        venue = request.form['venue']
        organizer = request.form['organizer']
        capacity = request.form['capacity']

        result = execute_query("""
            INSERT INTO events 
            (title, description, date, time, venue, organizer, capacity, registered_count, created_at) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, 0, CURRENT_TIMESTAMP)
        """, (title, description, date, time, venue, organizer, capacity))
        
        if result is None:
            flash('Database error! Event not created.', 'error')
            return redirect(url_for('create_event'))

        flash('Event created successfully!', 'success')
        return redirect(url_for('admin_events'))

    return render_template('create_event.html')

# Edit Event
@app.route('/admin/edit_event/<int:event_id>', methods=['GET', 'POST'])
def edit_event(event_id):
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))

    event = execute_query("SELECT * FROM events WHERE id = %s", (event_id,), fetch=True)

    if not event:
        flash("Event not found!", "error")
        return redirect(url_for('admin_events'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        date = request.form['date']
        time = request.form['time']
        venue = request.form['venue']
        organizer = request.form['organizer']
        capacity = request.form['capacity']

        execute_query("""
            UPDATE events
            SET title = %s, description = %s, date = %s, time = %s, venue = %s, organizer = %s, capacity = %s
            WHERE id = %s
        """, (title, description, date, time, venue, organizer, capacity, event_id))

        flash("Event updated successfully!", "success")
        return redirect(url_for('admin_events'))

    return render_template('edit_event.html', event=event)

# Delete Event
@app.route('/admin/delete_event/<int:event_id>')
def delete_event(event_id):
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))

    event = execute_query("SELECT * FROM events WHERE id = %s", (event_id,), fetch=True)

    if not event:
        flash("Event not found!", "error")
        return redirect(url_for('admin_events'))

    execute_query("DELETE FROM events WHERE id = %s", (event_id,))

    flash("Event deleted successfully!", "success")
    return redirect(url_for('admin_events'))

# View event registrations (admin)
@app.route('/admin/event_registrations/<int:event_id>')
def event_registrations(event_id):
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))

    event = execute_query("SELECT * FROM events WHERE id = %s", (event_id,), fetch=True)
    registrations = execute_query(
        """SELECT r.*, s.name, s.student_id, s.department, s.year
           FROM registrations r
           JOIN students s ON r.student_id = s.id
           WHERE r.event_id = %s
           ORDER BY r.registration_time""",
        (event_id,), fetchall=True) or []

    return render_template('event_registrations.html', event=event, registrations=registrations)

# -----------------------
# Export helpers
# -----------------------
def make_dataframe_from_regs(regs):
    """Return a pandas DataFrame from registration records."""
    rows = []
    for r in regs:
        rows.append({
            'Student Name': r.get('name', ''),
            'Student ID': r.get('student_id', ''),
            'Department': r.get('department', ''),
            'Year': r.get('year', ''),
            'Registration Time': r.get('registration_time', ''),
            'Attended': 'Yes' if r.get('attended') else 'No',
            'Check-in Time': r.get('checkin_time', '') if r.get('checkin_time') else ''
        })
    return pd.DataFrame(rows)

def dataframe_to_excel_bytes(df, sheet_name='Sheet1'):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    output.seek(0)
    return output

def dataframe_to_pdf_bytes(df, title='Export'):
    if not REPORTLAB_AVAILABLE:
        raise ImportError("reportlab not installed")

    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(A4),
                            leftMargin=15, rightMargin=15,
                            topMargin=20, bottomMargin=20)

    styles = getSampleStyleSheet()
    elements = [Paragraph(title, styles['Heading2']), Spacer(1, 12)]

    # Convert DataFrame to list of lists
    data = [list(df.columns)]
    for _, row in df.iterrows():
        data.append([str(x) if not pd.isna(x) else '' for x in row])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c7be5')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
    ]))

    elements.append(table)
    doc.build(elements)

    output.seek(0)
    return output

def dataframe_to_csv_bytes(df):
    output = io.StringIO()
    df.to_csv(output, index=False, encoding='utf-8')
    output.seek(0)
    return output.getvalue()

# Event-specific export route
@app.route('/admin/event_registrations_export/<int:event_id>')
def export_event_registrations(event_id):
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))

    fmt = request.args.get('format', 'csv').lower()
    attendance_only = request.args.get('attendance_only', '0') in ('1', 'true', 'True')

    # Fetch registrations with join to students
    query = """SELECT r.*, s.name, s.student_id, s.department, s.year
               FROM registrations r
               JOIN students s ON r.student_id = s.id
               WHERE r.event_id = %s"""
    params = [event_id]
    if attendance_only:
        query += " AND r.attended = TRUE"
    query += " ORDER BY r.registration_time"

    regs = execute_query(query, params, fetchall=True) or []

    df = make_dataframe_from_regs(regs)
    event = execute_query("SELECT * FROM events WHERE id = %s", (event_id,), fetch=True)
    event_title_clean = event['title'].replace(' ', '_') if event and 'title' in event else f"event_{event_id}"

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{event_title_clean}_registrations_{timestamp}"

    if fmt == 'csv':
        output = io.StringIO()
        df.to_csv(output, index=False, encoding='utf-8')
        csv_text = output.getvalue()
        csv_bytes = ('\ufeff' + csv_text).encode('utf-8')
        csv_filename = f"{filename}.csv"
        return Response(csv_bytes, mimetype="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f"attachment;filename={csv_filename}"})

    elif fmt == 'excel':
        try:
            excel_io = dataframe_to_excel_bytes(df, sheet_name='Registrations')
            excel_filename = f"{filename}.xlsx"
            return send_file(excel_io, as_attachment=True, download_name=excel_filename,
                             mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        except Exception as e:
            flash('Excel export failed (missing library?). Falling back to CSV.', 'warning')
            output = io.StringIO()
            df.to_csv(output, index=False, encoding='utf-8')
            csv_bytes = ('\ufeff' + output.getvalue()).encode('utf-8')
            csv_filename = f"{filename}.csv"
            return Response(csv_bytes, mimetype="text/csv; charset=utf-8",
                            headers={"Content-Disposition": f"attachment;filename={csv_filename}"})

    elif fmt == 'pdf':
        try:
            pdf_io = dataframe_to_pdf_bytes(df, title=f"Registrations - {event['title'] if event and 'title' in event else event_title_clean}")
            pdf_filename = f"{filename}.pdf"
            return send_file(pdf_io, as_attachment=True, download_name=pdf_filename, mimetype='application/pdf')
        except Exception as e:
            flash('PDF generation not available. Falling back to CSV.', 'warning')
            output = io.StringIO()
            df.to_csv(output, index=False, encoding='utf-8')
            csv_bytes = ('\ufeff' + output.getvalue()).encode('utf-8')
            csv_filename = f"{filename}.csv"
            return Response(csv_bytes, mimetype="text/csv; charset=utf-8",
                            headers={"Content-Disposition": f"attachment;filename={csv_filename}"})
    else:
        flash('Unknown format requested. Supported: csv, excel, pdf', 'error')
        return redirect(url_for('event_registrations', event_id=event_id))

# Attendance-only export for all events (admin)
@app.route('/admin/export/attendance_all')
def export_attendance_all():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))

    fmt = request.args.get('format', 'csv').lower()
    query = """SELECT r.*, s.name, s.student_id, s.department, s.year, e.title as event_title, e.date as event_date
               FROM registrations r
               JOIN students s ON r.student_id = s.id
               JOIN events e ON r.event_id = e.id
               WHERE r.attended = TRUE
               ORDER BY r.checkin_time DESC"""
    records = execute_query(query, fetchall=True) or []

    # Convert to a DataFrame
    rows = []
    for r in records:
        rows.append({
            'Student Name': r.get('name', ''),
            'Student ID': r.get('student_id', ''),
            'Department': r.get('department', ''),
            'Year': r.get('year', ''),
            'Event Title': r.get('event_title', ''),
            'Event Date': r.get('event_date', ''),
            'Check-in Time': r.get('checkin_time', '') if r.get('checkin_time') else '',
        })
    df = pd.DataFrame(rows)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    base_filename = f"attendance_all_{timestamp}"
    if fmt == 'csv':
        output = io.StringIO()
        df.to_csv(output, index=False, encoding='utf-8')
        csv_bytes = ('\ufeff' + output.getvalue()).encode('utf-8')
        filename = f"{base_filename}.csv"
        return Response(csv_bytes, mimetype="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f"attachment;filename={filename}"})
    elif fmt == 'excel':
        try:
            excel_io = dataframe_to_excel_bytes(df, sheet_name='Attendance')
            filename = f"{base_filename}.xlsx"
            return send_file(excel_io, as_attachment=True, download_name=filename,
                             mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        except Exception:
            flash('Excel export not available. Falling back to CSV.', 'warning')
            output = io.StringIO()
            df.to_csv(output, index=False, encoding='utf-8')
            csv_bytes = ('\ufeff' + output.getvalue()).encode('utf-8')
            filename = f"{base_filename}.csv"
            return Response(csv_bytes, mimetype="text/csv; charset=utf-8",
                            headers={"Content-Disposition": f"attachment;filename={filename}"})
    elif fmt == 'pdf':
        try:
            pdf_io = dataframe_to_pdf_bytes(df, title='Attendance Records')
            filename = f"{base_filename}.pdf"
            return send_file(pdf_io, as_attachment=True, download_name=filename, mimetype='application/pdf')
        except Exception:
            flash('PDF export not available. Falling back to CSV.', 'warning')
            output = io.StringIO()
            df.to_csv(output, index=False, encoding='utf-8')
            csv_bytes = ('\ufeff' + output.getvalue()).encode('utf-8')
            filename = f"{base_filename}.csv"
            return Response(csv_bytes, mimetype="text/csv; charset=utf-8",
                            headers={"Content-Disposition": f"attachment;filename={filename}"})
    else:
        flash('Unknown format', 'error')
        return redirect(url_for('admin_dashboard'))

# Mark attendance (AJAX)
@app.route('/admin/mark_attendance', methods=['POST'])
def admin_mark_attendance():
    if 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'Admin login required'})

    student_id = request.json.get('student_id')
    event_id = request.json.get('event_id')
    attended = request.json.get('attended', False)

    # Find student internal id from students table by student_id
    student = execute_query("SELECT * FROM students WHERE student_id = %s", (student_id,), fetch=True)
    if not student:
        return jsonify({'success': False, 'message': 'Student not found'})

    try:
        checkin_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S') if attended else None
        if attended:
            execute_query("UPDATE registrations SET attended = TRUE, checkin_time = %s WHERE student_id = %s AND event_id = %s", (checkin_time, student['id'], event_id))
        else:
            execute_query("UPDATE registrations SET attended = FALSE, checkin_time = NULL WHERE student_id = %s AND event_id = %s", (student['id'], event_id))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

<<<<<<< HEAD

# -----------------------
# Logout Routes
# -----------------------

# Student logout
=======
# -----------------------
# Student Logout - Add this new route
# -----------------------
>>>>>>> 5fcf06c7a616f04a973d34835cf85ac0694be57e
@app.route('/logout')
def logout():
    # Clear student session data
    session.pop('student_id', None)
    session.pop('student_name', None)
    flash('Logged out successfully!', 'success')
    return redirect(url_for('index'))

# Admin logout
@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_id', None)
    session.pop('admin_name', None)
    flash('Admin logged out successfully!', 'success')
    return redirect(url_for('admin_login'))


# Run
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
<<<<<<< HEAD
    app.run(host='0.0.0.0', port=port, debug=False)
=======
    app.run(host='0.0.0.0', port=port, debug=False)
>>>>>>> 5fcf06c7a616f04a973d34835cf85ac0694be57e
