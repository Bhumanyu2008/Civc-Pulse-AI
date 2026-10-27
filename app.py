from flask import Flask, render_template, request, jsonify, session
import sqlite3
from datetime import datetime, timedelta
from math import radians, cos, sin, asin, sqrt
from database import get_db, init_db

app = Flask(__name__, template_folder='.', static_folder='.')
app.secret_key = "civicpulse_secret_superkey"

# Predefined municipal credentials
GOVT_ACCESS_CODE = "ADMIN2026"
DEPT_ACCOUNTS = {
    "pwd_officer": "pwd123",
    "sanitation_officer": "clean123",
    "water_officer": "water123"
}

DEPT_RULES = {
    'Roads': {'dept': 'Public Works Dept (PWD)', 'sla_hours': 48},
    'Sanitation': {'dept': 'Sanitation Department', 'sla_hours': 24},
    'Electricity': {'dept': 'Electricity Board', 'sla_hours': 12},
    'Water': {'dept': 'Water Supply Board', 'sla_hours': 24}
}

# ----------------- CITIZEN FACING (PUBLIC) ----------------- #

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/complaints', methods=['POST'])
def add_complaint():
    """Any citizen with the public link can submit without login"""
    data = request.get_json() or request.form
    name = data.get('citizen_name', 'Anonymous Citizen')
    phone = data.get('phone', '0000000000')
    category = data.get('category', 'Roads')
    desc = data.get('description', '')
    lat = float(data.get('latitude', 28.6139))
    lon = float(data.get('longitude', 77.2090))

    dept_info = DEPT_RULES.get(category, {'dept': 'General Administration', 'sla_hours': 48})
    deadline = (datetime.now() + timedelta(hours=dept_info['sla_hours'])).strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO complaints (citizen_name, phone, category, description, latitude, longitude, assigned_dept, deadline)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (name, phone, category, desc, lat, lon, dept_info['dept'], deadline))
    complaint_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({"status": "success", "complaint_id": complaint_id})

# ----------------- AUTHORITY FACING (RESTRICTED) ----------------- #

@app.route('/api/auth/verify', methods=['POST'])
def verify_authority():
    """Checks the passcode entered by municipal staff"""
    data = request.get_json() or {}
    code = data.get('access_code', '')
    
    if code == GOVT_ACCESS_CODE or code in DEPT_ACCOUNTS.values():
        return jsonify({"authorized": True, "role": "Authority"})
    return jsonify({"authorized": False, "error": "Invalid clearance passkey"}), 401

@app.route('/api/authority/complaints', methods=['POST'])
def get_authority_complaints():
    """Returns complaints ONLY if valid authority passkey is supplied"""
    data = request.get_json() or {}
    code = data.get('access_code', '')

    if code != GOVT_ACCESS_CODE and code not in DEPT_ACCOUNTS.values():
        return jsonify({"error": "Unauthorized"}), 403

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM complaints ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/authority/assign/<int:complaint_id>', methods=['POST'])
def assign_department(complaint_id):
    """Authority sends/reassigns complaint to a specific field department"""
    data = request.get_json() or {}
    code = data.get('access_code', '')
    new_dept = data.get('target_department')

    if code != GOVT_ACCESS_CODE:
        return jsonify({"error": "Unauthorized"}), 403

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE complaints 
        SET assigned_dept = ?, status = 'IN_PROGRESS' 
        WHERE id = ?
    ''', (new_dept, complaint_id))
    conn.commit()
    conn.close()

    return jsonify({"status": "assigned", "complaint_id": complaint_id, "new_dept": new_dept})

if __name__ == '__main__':
    init_db()
    app.run(debug=True)