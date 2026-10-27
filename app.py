from flask import Flask, render_template, request, jsonify, redirect, url_for
import sqlite3
from datetime import datetime, timedelta
from math import radians, cos, sin, asin, sqrt
from database import get_db, init_db

# Configure Flask to read index.html directly from your current folder
app = Flask(__name__, template_folder='.', static_folder='.')
app.secret_key = "civicpulse_secret_key"

DEPT_RULES = {
    'Roads': {'dept': 'Public Works Dept (PWD)', 'sla_hours': 48},
    'Sanitation': {'dept': 'Sanitation Department', 'sla_hours': 24},
    'Electricity': {'dept': 'Electricity Board', 'sla_hours': 12},
    'Water': {'dept': 'Water Supply Board', 'sla_hours': 24}
}

def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371000  # meters
    dLat, dLon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dLat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dLon/2)**2
    return 2 * R * asin(sqrt(a))

def check_duplicate(category, lat, lon, threshold_meters=150):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, latitude, longitude FROM complaints WHERE category = ? AND status IN ('OPEN', 'IN_PROGRESS')", (category,))
    active_reports = cursor.fetchall()
    conn.close()

    for report in active_reports:
        dist = haversine_distance(lat, lon, report['latitude'], report['longitude'])
        if dist <= threshold_meters:
            return report['id']
    return None

def check_sla_breaches():
    conn = get_db()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute('''
        SELECT id, category, assigned_dept FROM complaints 
        WHERE status IN ('OPEN', 'IN_PROGRESS') AND deadline < ?
    ''', (now_str,))
    overdue_items = cursor.fetchall()

    for item in overdue_items:
        cursor.execute("UPDATE complaints SET status = 'ESCALATED' WHERE id = ?", (item['id'],))
        cursor.execute('''
            INSERT INTO escalations (complaint_id, reason, escalated_to)
            VALUES (?, 'SLA_BREACH: Department missed deadline', 'Municipal Commissioner')
        ''', (item['id'],))
    conn.commit()
    conn.close()

# ----------------- ROUTES ----------------- #

@app.route('/')
def home():
    check_sla_breaches()
    return render_template('index.html')

# API: Fetch all complaints for your teammate's dashboard JS
@app.route('/api/complaints', methods=['GET'])
def get_complaints():
    check_sla_breaches()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM complaints ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return jsonify([dict(ix) for ix in rows])

# API: Submit a new citizen report (with auto duplicate detection & SLA assignment)
@app.route('/api/complaints', methods=['POST'])
def add_complaint():
    data = request.get_json() or request.form
    name = data.get('citizen_name', 'Anonymous Citizen')
    phone = data.get('phone', '0000000000')
    category = data.get('category', 'Roads')
    desc = data.get('description', 'Reported issue')
    lat = float(data.get('latitude', 28.6139))
    lon = float(data.get('longitude', 77.2090))

    duplicate_id = check_duplicate(category, lat, lon)
    dept_info = DEPT_RULES.get(category, {'dept': 'Public Works Dept (PWD)', 'sla_hours': 48})
    deadline = (datetime.now() + timedelta(hours=dept_info['sla_hours'])).strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO complaints (citizen_name, phone, category, description, latitude, longitude, assigned_dept, deadline, parent_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (name, phone, category, desc, lat, lon, dept_info['dept'], deadline, duplicate_id))
    complaint_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({
        "status": "success",
        "complaint_id": complaint_id,
        "is_duplicate": duplicate_id is not None,
        "parent_id": duplicate_id,
        "assigned_dept": dept_info['dept'],
        "deadline": deadline
    })

# API: Department closes complaint
@app.route('/api/resolve/<int:complaint_id>', methods=['POST'])
def resolve_complaint(complaint_id):
    notes = request.json.get('notes', 'Resolved by field staff.') if request.is_json else 'Resolved'
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE complaints SET status = 'RESOLVED', resolution_notes = ? WHERE id = ?", (notes, complaint_id))
    conn.commit()
    conn.close()
    return jsonify({"status": "resolved", "complaint_id": complaint_id})

# API: Evidence contradicts closure -> Auto-reopen & escalate
@app.route('/api/dispute/<int:complaint_id>', methods=['POST'])
def dispute_complaint(complaint_id):
    reason = request.json.get('reason', 'Citizen verification failed.') if request.is_json else 'Disputed'
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE complaints SET status = 'DISPUTED' WHERE id = ?", (complaint_id,))
    cursor.execute('''
        INSERT INTO escalations (complaint_id, reason, escalated_to)
        VALUES (?, ?, 'Municipal Commissioner & Vigilance Bureau')
    ''', (complaint_id, f"FALSE CLOSURE EVIDENCE: {reason}"))
    conn.commit()
    conn.close()
    return jsonify({"status": "disputed_and_escalated", "complaint_id": complaint_id})

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)