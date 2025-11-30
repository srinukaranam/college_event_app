from flask import Blueprint, render_template, request, jsonify, session, flash, redirect, url_for
from datetime import datetime
from qr_database import execute_query, init_qr_tables

qr_bp = Blueprint('qr', __name__)

@qr_bp.route('/qr_scanner')
def qr_scanner():
    """QR Scanner page - Admin only"""
    if 'admin_id' not in session:
        flash('Access denied. Admin access required.', 'error')
        return redirect(url_for('admin_login'))
    
    return render_template('qr_scanner.html')

@qr_bp.route('/qr_verify', methods=['POST'])
def qr_verify():
    """Verify QR code - Admin only"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'Admin access required'})
    
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
        
        # Extract information from QR data
        event_title = qr_dict.get('Event', '')
        student_id_str = qr_dict.get('Student ID', '')
        
        if not event_title or not student_id_str:
            return jsonify({'success': False, 'message': 'Invalid QR code format'})
        
        # Get student by student_id
        student = execute_query(
            "SELECT * FROM students WHERE student_id = ?", 
            (student_id_str,), 
            fetch=True
        )
        
        # Get event by title
        event = execute_query(
            "SELECT * FROM events WHERE title = ?", 
            (event_title,), 
            fetch=True
        )
        
        if not student:
            return jsonify({'success': False, 'message': 'Student not found'})
        
        if not event:
            return jsonify({'success': False, 'message': 'Event not found'})
        
        # Check if student is registered for this event
        registration = execute_query(
            "SELECT * FROM registrations WHERE student_id = ? AND event_id = ?", 
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
            "UPDATE registrations SET attended = TRUE, checkin_time = ? WHERE student_id = ? AND event_id = ?",
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
        print(f"QR verification error: {str(e)}")
        return jsonify({'success': False, 'message': f'Error processing QR code: {str(e)}'})

@qr_bp.route('/qr_verification_page', methods=['GET', 'POST'])
def qr_verification_page():
    """QR Verification page with manual entry - Admin only"""
    if 'admin_id' not in session:
        flash('Access denied. Admin access required.', 'error')
        return redirect(url_for('admin_login'))
    
    if request.method == 'POST':
        qr_data = request.form.get('qr_data')
        
        if not qr_data:
            return render_template('qr_verification.html', 
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
                return render_template('qr_verification.html', 
                                     success=False, 
                                     message='Invalid QR code format')
            
            # Get student by student_id
            student = execute_query(
                "SELECT * FROM students WHERE student_id = ?", 
                (student_id_str,), 
                fetch=True
            )
            
            # Get event by title
            event = execute_query(
                "SELECT * FROM events WHERE title = ?", 
                (event_title,), 
                fetch=True
            )
            
            if not student:
                return render_template('qr_verification.html', 
                                     success=False, 
                                     message='Student not found')
            
            if not event:
                return render_template('qr_verification.html', 
                                     success=False, 
                                     message='Event not found')
            
            # Check if student is registered for this event
            registration = execute_query(
                "SELECT * FROM registrations WHERE student_id = ? AND event_id = ?", 
                (student['id'], event['id']), 
                fetch=True
            )
            
            if not registration:
                return render_template('qr_verification.html', 
                                     success=False, 
                                     message='Student not registered for this event')
            
            # Check if already attended
            if registration['attended']:
                return render_template('qr_verification.html',
                                     success=False,
                                     message=f"Student {student['name']} has already checked in for this event")
            
            # Mark as attended with timestamp
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            execute_query(
                "UPDATE registrations SET attended = TRUE, checkin_time = ? WHERE student_id = ? AND event_id = ?",
                (current_time, student['id'], event['id'])
            )
            
            return render_template('qr_verification.html',
                                 success=True,
                                 student=student,
                                 event=event,
                                 checkin_time=current_time)
            
        except Exception as e:
            print(f"QR verification error: {str(e)}")
            return render_template('qr_verification.html', 
                                 success=False, 
                                 message=f'Error processing QR code: {str(e)}')
    
    # GET request - show recent verifications
    recent_verifications = execute_query(
        """SELECT s.name, s.student_id, e.title, r.checkin_time 
           FROM registrations r 
           JOIN students s ON r.student_id = s.id 
           JOIN events e ON r.event_id = e.id 
           WHERE r.attended = TRUE 
           ORDER BY r.checkin_time DESC 
           LIMIT 10""",
        fetchall=True
    )
    
    return render_template('qr_verification.html', recent_verifications=recent_verifications)

@qr_bp.route('/qr_verification_history')
def qr_verification_history():
    """Verification history page - Admin only"""
    if 'admin_id' not in session:
        flash('Access denied. Admin access required.', 'error')
        return redirect(url_for('admin_login'))
    
    # Get all verifications
    verifications = execute_query(
        """SELECT s.name, s.student_id, s.department, e.title, e.date, r.checkin_time 
           FROM registrations r 
           JOIN students s ON r.student_id = s.id 
           JOIN events e ON r.event_id = e.id 
           WHERE r.attended = TRUE 
           ORDER BY r.checkin_time DESC""",
        fetchall=True
    )
    
    return render_template('qr_verification_history.html', verifications=verifications)