import csv
import io
import os
import traceback
import psycopg2
import base64
from datetime import datetime, date
from io import BytesIO

from flask import (
    Flask, Response, flash, jsonify, redirect, render_template,
    request, send_file, session, url_for
)

import qrcode
import pandas as pd

# Optional PDF library
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, landscape, A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key_here')
app.config['UPLOAD_FOLDER'] = 'static/qrcodes'

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# -----------------------
# Jinja2 Filters for Date Handling
# -----------------------

@app.template_filter('format_date')
def format_date_filter(value, format_str='%Y-%m-%d'):
    """Format a date in Jinja2 templates"""
    if isinstance(value, (date, datetime)):
        return value.strftime(format_str)
    elif isinstance(value, str):
        try:
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
# Database Configuration
# -----------------------
def get_db_connection():
    """Get PostgreSQL database connection from Render"""
    database_url = os.environ.get('DATABASE_URL')
    
    if not database_url:
        print("WARNING: DATABASE_URL not set.")
        return None
    
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    try:
        conn = psycopg2.connect(database_url, sslmode='require')
        print("✅ Connected to PostgreSQL successfully")
        return conn
    except Exception as e:
        print(f"❌ Error connecting to PostgreSQL: {e}")
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
# Database Initialization
# -----------------------
def check_and_init_database():
    """Check if database tables exist, create if not"""
    try:
        print("🔍 Checking database tables...")
        
        conn = get_db_connection()
        if conn is None:
            print("❌ Cannot connect to database")
            return False
        
        cursor = conn.cursor()
        
        # Create tables if they don't exist
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
        
        # Insert default admin if not exists
        cursor.execute("""
            INSERT INTO admins (username, password, name) 
            VALUES ('admin', 'admin123', 'System Administrator')
            ON CONFLICT (username) DO NOTHING
        """)
        
        # Insert default staff if not exists
        cursor.execute("""
            INSERT INTO staff (username, password, name) 
            VALUES ('staff', 'staff123', 'Event Staff')
            ON CONFLICT (username) DO NOTHING
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ Database initialization complete")
        return True
        
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        return False

# Initialize database when app starts
print("🚀 Starting application...")
with app.app_context():
    check_and_init_database()


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
        
        existing_student = execute_query(
            "SELECT * FROM students WHERE student_id = %s OR email = %s", 
            (student_id, email), 
            fetch=True
        )
        
        if existing_student:
            flash('Student ID or Email already exists!', 'error')
            return redirect(url_for('register'))
        
        execute_query(
            "INSERT INTO students (student_id, name, email, password, department, year) VALUES (%s, %s, %s, %s, %s, %s)",
            (student_id, name, email, password, department, year)
        )
        
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
    
    registration = execute_query(
        "SELECT * FROM registrations WHERE student_id = %s AND event_id = %s", 
        (session['student_id'], event_id), 
        fetch=True
    )
    
    return render_template('event_details.html', event=event, registration=registration)

# Register for event
@app.route('/register_event/<int:event_id>')
def register_event(event_id):
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
    
    if event['registered_count'] >= event['capacity']:
        flash('Event is full!', 'error')
        return redirect(url_for('event_details', event_id=event_id))
    
    existing_registration = execute_query(
        "SELECT * FROM registrations WHERE student_id = %s AND event_id = %s", 
        (session['student_id'], event_id), 
        fetch=True
    )
    
    if existing_registration:
        flash('You are already registered for this event!', 'error')
        return redirect(url_for('event_details', event_id=event_id))
    
    student = execute_query(
        "SELECT * FROM students WHERE id = %s", 
        (session['student_id'],), 
        fetch=True
    )
    
    if not student:
        flash('Student not found!', 'error')
        return redirect(url_for('events'))
    
    try:
        qr_data = f"""
Event: {event['title']}
Student: {student['name']}
Student ID: {student['student_id']}
Event Date: {event['date']}
Event Time: {event['time']}
Venue: {event['venue']}
Registration ID: {student['student_id']}_{event_id}
        """.strip()
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        buffer = BytesIO()
        qr_img.save(buffer, format="PNG")
        buffer.seek(0)
        
        qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        qr_web_path = f"data:image/png;base64,{qr_base64}"
        
        execute_query(
            "INSERT INTO registrations (student_id, event_id, qr_code_path) VALUES (%s, %s, %s)",
            (session['student_id'], event_id, qr_web_path)
        )
        
        execute_query(
            "UPDATE events SET registered_count = registered_count + 1 WHERE id = %s",
            (event_id,)
        )
        
        flash('Successfully registered for the event! QR code generated.', 'success')
        return redirect(url_for('event_details', event_id=event_id))
        
    except Exception as e:
        print(f"Error in register_event: {str(e)}")
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

# Staff QR verification
@app.route('/staff/verify', methods=['POST'])
def staff_verify():
    if 'staff_id' not in session:
        return jsonify({'success': False, 'message': 'Staff access required'})
    
    qr_data = request.json.get('qr_data')
    
    if not qr_data:
        return jsonify({'success': False, 'message': 'No QR data provided'})
    
    try:
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
        
        student = execute_query(
            "SELECT * FROM students WHERE student_id = %s", 
            (student_id_str,), 
            fetch=True
        )
        
        event = execute_query(
            "SELECT * FROM events WHERE title = %s", 
            (event_title,), 
            fetch=True
        )
        
        if not student:
            return jsonify({'success': False, 'message': 'Student not found'})
        
        if not event:
            return jsonify({'success': False, 'message': 'Event not found'})
        
        registration = execute_query(
            "SELECT * FROM registrations WHERE student_id = %s AND event_id = %s", 
            (student['id'], event['id']), 
            fetch=True
        )
        
        if not registration:
            return jsonify({'success': False, 'message': 'Student not registered for this event'})
        
        if registration['attended']:
            return jsonify({
                'success': False, 
                'message': f"Student {student['name']} has already checked in for this event"
            })
        
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

# Admin events
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

        execute_query("""
            INSERT INTO events 
            (title, description, date, time, venue, organizer, capacity, registered_count, created_at) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, 0, CURRENT_TIMESTAMP)
        """, (title, description, date, time, venue, organizer, capacity))

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

# View event registrations
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
# Admin: Export All Attendance
# -----------------------
# Replace the current export_attendance_all function with this fixed version:

@app.route('/admin/export/attendance_all')
def export_attendance_all():
    """Enhanced export function for attendance records"""
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))

    fmt = request.args.get('format', 'csv').lower()
    
    # Fetch all attendance records with proper error handling
    try:
        query = """SELECT 
                s.name as student_name,
                s.student_id,
                s.department,
                s.year,
                e.title as event_title,
                TO_CHAR(e.date, 'YYYY-MM-DD') as event_date,
                e.time as event_time,
                e.venue,
                TO_CHAR(r.checkin_time, 'YYYY-MM-DD HH24:MI:SS') as checkin_time,
                TO_CHAR(r.registration_time, 'YYYY-MM-DD HH24:MI:SS') as registration_time
            FROM registrations r
            JOIN students s ON r.student_id = s.id
            JOIN events e ON r.event_id = e.id
            WHERE r.attended = TRUE
            ORDER BY r.checkin_time DESC"""
        
        records = execute_query(query, fetchall=True) or []

        if not records:
            flash('No attendance records found!', 'warning')
            return redirect(url_for('admin_dashboard'))
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"attendance_export_{timestamp}"
        
        # CSV Export
        if fmt == 'csv':
            return export_csv(records, filename)
        
        # Excel Export
        elif fmt == 'excel':
            return export_excel(records, filename)
        
        # PDF Export
        elif fmt == 'pdf':
            return export_pdf(records, filename)
        
        else:
            flash('Unknown export format. Using CSV.', 'warning')
            return export_csv(records, filename)
            
    except Exception as e:
        flash(f'Export error: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))

# -----------------------
# Export Event Registrations
# -----------------------
@app.route('/admin/event_registrations_export/<int:event_id>')
def event_registrations_export(event_id):
    """Export registrations for a specific event"""
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    
    fmt = request.args.get('format', 'csv').lower()
    attendance_only = request.args.get('attendance_only', '0') == '1'
    
    try:
        # Fetch event details
        event = execute_query(
            "SELECT * FROM events WHERE id = %s",
            (event_id,), fetch=True
        )
        
        if not event:
            flash('Event not found!', 'error')
            return redirect(url_for('admin_events'))
        
        # Build query based on attendance filter
        if attendance_only:
            query = """SELECT 
                    s.name, s.student_id, s.department, s.year,
                    TO_CHAR(r.registration_time, 'YYYY-MM-DD HH24:MI:SS') as registration_time,
                    TO_CHAR(r.checkin_time, 'YYYY-MM-DD HH24:MI:SS') as checkin_time,
                    r.attended
                FROM registrations r
                JOIN students s ON r.student_id = s.id
                WHERE r.event_id = %s AND r.attended = TRUE
                ORDER BY r.checkin_time DESC"""
        else:
            query = """SELECT 
                    s.name, s.student_id, s.department, s.year,
                    TO_CHAR(r.registration_time, 'YYYY-MM-DD HH24:MI:SS') as registration_time,
                    TO_CHAR(r.checkin_time, 'YYYY-MM-DD HH24:MI:SS') as checkin_time,
                    r.attended
                FROM registrations r
                JOIN students s ON r.student_id = s.id
                WHERE r.event_id = %s
                ORDER BY r.registration_time DESC"""
        
        records = execute_query(query, (event_id,), fetchall=True) or []
        
        if not records:
            flash(f'No records found for {event["title"]}!', 'warning')
            return redirect(url_for('event_registrations', event_id=event_id))
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_title = "".join(c for c in event['title'] if c.isalnum() or c in (' ', '-', '_')).rstrip()
        filename = f"{safe_title}_registrations_{timestamp}"
        
        if fmt == 'csv':
            return export_event_csv(records, event, filename)
        elif fmt == 'excel':
            return export_event_excel(records, event, filename)
        elif fmt == 'pdf':
            return export_event_pdf(records, event, filename)
        else:
            return export_event_csv(records, event, filename)
            
    except Exception as e:
        flash(f'Export error: {str(e)}', 'error')
        return redirect(url_for('event_registrations', event_id=event_id))

def export_event_csv(records, event, filename):
    """Export event registrations to CSV"""
    try:
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'Event:', event['title'],
            'Date:', str(event['date']),
            'Time:', str(event['time']),
            'Venue:', event['venue']
        ])
        writer.writerow([])  # Empty row
        writer.writerow(['Student Name', 'Student ID', 'Department', 'Year', 
                        'Registration Time', 'Check-in Time', 'Status'])
        
        # Write data
        for record in records:
            writer.writerow([
                record.get('name', ''),
                record.get('student_id', ''),
                record.get('department', ''),
                record.get('year', ''),
                record.get('registration_time', ''),
                record.get('checkin_time', '') if record.get('checkin_time') else 'Not checked in',
                'Attended' if record.get('attended') else 'Registered'
            ])
        
        # Add summary
        writer.writerow([])
        writer.writerow(['Summary:', f'Total: {len(records)}', 
                        f'Attended: {len([r for r in records if r.get("attended")])}',
                        f'Pending: {len([r for r in records if not r.get("attended")])}'])
        
        response = Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={
                "Content-Disposition": f"attachment;filename={filename}.csv"
            }
        )
        return response
        
    except Exception as e:
        flash(f'CSV export error: {str(e)}', 'error')
        return redirect(url_for('event_registrations', event_id=event['id']))

def export_event_excel(records, event, filename):
    """Export event registrations to Excel"""
    try:
        # Prepare data
        data = []
        for record in records:
            data.append({
                'Student Name': record.get('name', ''),
                'Student ID': record.get('student_id', ''),
                'Department': record.get('department', ''),
                'Year': record.get('year', ''),
                'Registration Time': record.get('registration_time', ''),
                'Check-in Time': record.get('checkin_time', '') if record.get('checkin_time') else 'Not checked in',
                'Status': 'Attended' if record.get('attended') else 'Registered'
            })
        
        df = pd.DataFrame(data)
        
        # Create Excel in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Write event info
            event_info = pd.DataFrame({
                'Event Information': [
                    f"Event: {event['title']}",
                    f"Date: {event['date']}",
                    f"Time: {event['time']}",
                    f"Venue: {event['venue']}",
                    f"Organizer: {event['organizer']}",
                    f"Capacity: {event['capacity']}",
                    f"Total Registrations: {len(records)}",
                    f"Attended: {len([r for r in records if r.get('attended')])}",
                    f"Pending: {len([r for r in records if not r.get('attended')])}"
                ]
            })
            event_info.to_excel(writer, index=False, sheet_name='Event Info')
            
            # Write registrations
            df.to_excel(writer, index=False, sheet_name='Registrations')
            
            # Auto-adjust column widths
            for sheet_name in writer.sheets:
                worksheet = writer.sheets[sheet_name]
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
        
        output.seek(0)
        
        return send_file(
            output,
            as_attachment=True,
            download_name=f"{filename}.xlsx",
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        flash(f'Excel export error: {str(e)}', 'error')
        return export_event_csv(records, event, filename)

def export_event_pdf(records, event, filename):
    """Export event registrations to PDF"""
    if not REPORTLAB_AVAILABLE:
        flash('PDF export requires ReportLab library', 'warning')
        return export_event_csv(records, event, filename)
    
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import landscape, A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        
        # Create PDF buffer
        pdf_buffer = BytesIO()
        
        # Create document
        doc = SimpleDocTemplate(
            pdf_buffer,
            pagesize=landscape(A4),
            leftMargin=20,
            rightMargin=20,
            topMargin=30,
            bottomMargin=30
        )
        
        elements = []
        styles = getSampleStyleSheet()
        
        # Add event title
        title = Paragraph(f"<b>Event Registrations: {event['title']}</b>", styles['Heading2'])
        elements.append(title)
        
        # Add event details
        details = Paragraph(
            f"<b>Date:</b> {event['date']} | <b>Time:</b> {event['time']} | "
            f"<b>Venue:</b> {event['venue']} | <b>Organizer:</b> {event['organizer']}<br/>"
            f"<b>Total Registrations:</b> {len(records)} | <b>Attended:</b> {len([r for r in records if r.get('attended')])} | "
            f"<b>Pending:</b> {len([r for r in records if not r.get('attended')])}",
            styles['Normal']
        )
        elements.append(details)
        elements.append(Spacer(1, 20))
        
        # Prepare table data
        if records:
            table_data = [['Student Name', 'Student ID', 'Department', 'Year', 
                          'Registration Time', 'Check-in Time', 'Status']]
            
            for record in records:
                table_data.append([
                    record.get('name', ''),
                    record.get('student_id', ''),
                    record.get('department', ''),
                    record.get('year', ''),
                    record.get('registration_time', ''),
                    record.get('checkin_time', '') if record.get('checkin_time') else 'Not checked in',
                    'Attended' if record.get('attended') else 'Registered'
                ])
            
            # Create table
            col_widths = [80, 60, 60, 30, 80, 80, 50]
            table = Table(table_data, colWidths=col_widths, repeatRows=1)
            
            # Style table
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            
            elements.append(table)
        else:
            elements.append(Paragraph("<i>No registrations found</i>", styles['Italic']))
        
        elements.append(Spacer(1, 20))
        
        # Add footer
        footer = Paragraph(
            f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
            f"Event ID: {event['id']}",
            styles['Normal']
        )
        elements.append(footer)
        
        # Build PDF
        doc.build(elements)
        pdf_buffer.seek(0)
        
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=f"{filename}.pdf",
            mimetype='application/pdf'
        )
        
    except Exception as e:
        flash(f'PDF export error: {str(e)}', 'error')
        return export_event_csv(records, event, filename)

# -----------------------
# Mark Attendance AJAX Endpoint
# -----------------------
@app.route('/admin/mark_attendance', methods=['POST'])
def mark_attendance():
    """AJAX endpoint to mark attendance"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        data = request.json
        student_id = data.get('student_id')
        event_id = data.get('event_id')
        attended = data.get('attended', False)
        
        # Get student by student_id (not id)
        student = execute_query(
            "SELECT id FROM students WHERE student_id = %s",
            (student_id,), fetch=True
        )
        
        if not student:
            return jsonify({'success': False, 'message': 'Student not found'})
        
        # Update attendance
        if attended:
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            execute_query(
                "UPDATE registrations SET attended = TRUE, checkin_time = %s "
                "WHERE student_id = %s AND event_id = %s",
                (current_time, student['id'], event_id)
            )
        else:
            execute_query(
                "UPDATE registrations SET attended = FALSE, checkin_time = NULL "
                "WHERE student_id = %s AND event_id = %s",
                (student['id'], event_id)
            )
        
        return jsonify({'success': True, 'message': 'Attendance updated'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

def export_csv(records, filename):
    """Export records to CSV format"""
    try:
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'Student Name', 'Student ID', 'Department', 'Year',
            'Event Title', 'Event Date', 'Event Time', 'Venue',
            'Registration Time', 'Check-in Time'
        ])
        
        # Write data
        for record in records:
            writer.writerow([
                record.get('student_name', ''),
                record.get('student_id', ''),
                record.get('department', ''),
                record.get('year', ''),
                record.get('event_title', ''),
                record.get('event_date', ''),
                record.get('event_time', ''),
                record.get('venue', ''),
                record.get('registration_time', ''),
                record.get('checkin_time', '')
            ])
        
        # Create response
        response = Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={
                "Content-Disposition": f"attachment;filename={filename}.csv",
                "Content-Type": "text/csv; charset=utf-8"
            }
        )
        return response
        
    except Exception as e:
        flash(f'CSV export error: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))

def export_excel(records, filename):
    """Export records to Excel format"""
    try:
        # Prepare data for DataFrame
        data = []
        for record in records:
            data.append({
                'Student Name': record.get('student_name', ''),
                'Student ID': record.get('student_id', ''),
                'Department': record.get('department', ''),
                'Year': record.get('year', ''),
                'Event Title': record.get('event_title', ''),
                'Event Date': record.get('event_date', ''),
                'Event Time': str(record.get('event_time', '')),
                'Venue': record.get('venue', ''),
                'Registration Time': record.get('registration_time', ''),
                'Check-in Time': record.get('checkin_time', '')
            })
        
        df = pd.DataFrame(data)
        
        # Create Excel in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Attendance')
            # Auto-adjust column widths
            worksheet = writer.sheets['Attendance']
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 30)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        output.seek(0)
        
        return send_file(
            output,
            as_attachment=True,
            download_name=f"{filename}.xlsx",
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        flash(f'Excel export error: {str(e)}. Please install: pip install openpyxl', 'error')
        # Fallback to CSV
        return export_csv(records, filename)

def export_pdf(records, filename):
    """Export records to PDF format"""
    if not REPORTLAB_AVAILABLE:
        flash('PDF export requires ReportLab library. Please install: pip install reportlab', 'warning')
        return export_csv(records, filename)
    
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import landscape, A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        
        # Create PDF in memory
        pdf_buffer = BytesIO()
        
        # Create document with landscape orientation
        doc = SimpleDocTemplate(
            pdf_buffer,
            pagesize=landscape(A4),
            leftMargin=20,
            rightMargin=20,
            topMargin=30,
            bottomMargin=30
        )
        
        elements = []
        styles = getSampleStyleSheet()
        
        # Add title
        title = Paragraph(f"<b>Attendance Report</b><br/>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", 
                         styles['Heading2'])
        elements.append(title)
        elements.append(Spacer(1, 20))
        
        # Prepare table data
        table_data = [[
            'Student Name', 'Student ID', 'Department', 'Year',
            'Event', 'Date', 'Time', 'Venue', 'Check-in Time'
        ]]
        
        for record in records:
            table_data.append([
                record.get('student_name', ''),
                record.get('student_id', ''),
                record.get('department', ''),
                record.get('year', ''),
                record.get('event_title', ''),
                record.get('event_date', ''),
                str(record.get('event_time', '')),
                record.get('venue', ''),
                record.get('checkin_time', '')
            ])
        
        # Add summary row
        table_data.append([
            f"<b>Total Records: {len(records)}</b>", "", "", "", "", "", "", "", ""
        ])
        
        # Create table with optimized column widths
        col_widths = [70, 50, 50, 30, 100, 50, 40, 60, 70]
        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        
        # Apply table styles
        table.setStyle(TableStyle([
            # Header style
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            
            # Data rows style
            ('BACKGROUND', (0, 1), (-1, -2), colors.white),
            ('TEXTCOLOR', (0, 1), (-1, -2), colors.black),
            ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -2), 8),
            ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            
            # Grid lines
            ('GRID', (0, 0), (-1, -2), 0.5, colors.grey),
            
            # Summary row style
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#ecf0f1')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, -1), (-1, -1), 9),
            ('ALIGN', (0, -1), (-1, -1), 'LEFT'),
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 20))
        
        # Build PDF
        doc.build(elements)
        pdf_buffer.seek(0)
        
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=f"{filename}.pdf",
            mimetype='application/pdf'
        )
        
    except Exception as e:
        flash(f'PDF export error: {str(e)}', 'error')
        # Fallback to CSV
        return export_csv(records, filename)


# Debug route
@app.route('/debug/db')
def debug_db():
    try:
        database_url = os.environ.get('DATABASE_URL', 'Not set')
        
        tables = {
            'students': execute_query("SELECT COUNT(*) as count FROM students", fetch=True),
            'events': execute_query("SELECT COUNT(*) as count FROM events", fetch=True),
            'registrations': execute_query("SELECT COUNT(*) as count FROM registrations", fetch=True),
            'staff': execute_query("SELECT COUNT(*) as count FROM staff", fetch=True),
            'admins': execute_query("SELECT COUNT(*) as count FROM admins", fetch=True)
        }
        
        recent_students = execute_query("SELECT student_id, name FROM students ORDER BY id DESC LIMIT 5", fetchall=True) or []
        recent_events = execute_query("SELECT title, date FROM events ORDER BY id DESC LIMIT 5", fetchall=True) or []
        
        return render_template('debug_db.html',
                             database_url=database_url,
                             tables=tables,
                             recent_students=recent_students,
                             recent_events=recent_events)
    except Exception as e:
        return f"Error: {str(e)}<br><pre>{traceback.format_exc()}</pre>"


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


# Logout routes
@app.route('/logout')
def logout():
    session.pop('student_id', None)
    session.pop('student_name', None)
    flash('Logged out successfully!', 'success')
    return redirect(url_for('index'))

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_id', None)
    session.pop('admin_name', None)
    flash('Admin logged out successfully!', 'success')
    return redirect(url_for('admin_login'))

# Run
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)