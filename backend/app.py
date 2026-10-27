import os
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, session
from database import get_db, init_db

app = Flask(__name__, template_folder='.', static_folder='.')
app.secret_key = "civicpulse_secret_superkey_2026"

# Municipal access codes
GOVT_ACCESS_CODE = "ADMIN2026"
DEPT_ACCOUNTS = {
    "pwd_officer": "pwd123",
    "sanitation_officer": "clean123",
    "water_officer": "water123",
    "electricity_officer": "power123"
}

# SLA and department routing rules
DEPT_RULES = {
    'Roads': {'dept': 'Public Works Dept (Roads & Potholes)', 'sla_hours': 48},
    'Sanitation': {'dept': 'Sanitation & Waste Management', 'sla_hours': 24},
    'Electricity': {'dept': 'Electricity Board', 'sla_hours': 12},
    'Water': {'dept': 'Municipal Water Board & Drainage', 'sla_hours': 24}
}

# ----------------- INITIALIZATION ----------------- #

# Ensure the database tables exist on server startup
with app.app_context():
    init_db()

# ----------------- PUBLIC CITIZEN ROUTES ----------------- #

@app.route('/')
def home():
    """Renders the main portal interface"""
    return render_template('index.html')

@app.route('/api/complaints', methods=['GET', 'POST'])
def manage_complaints():
    """
    GET:  Returns all complaints ordered newest-first (used by both citizen feed & authority dashboard)
    POST: Inserts a new citizen complaint into the central database
    """
    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'GET':
        cursor.execute("SELECT * FROM complaints ORDER BY id DESC")
        rows = cursor.fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows]), 200

    if request.method == 'POST':
        data = request.get_json(silent=True) or request.form.to_dict() or {}
        
        name = data.get('citizen_name', 'Citizen')
        phone = data.get('phone', '9876543210')
        category = data.get('category', 'Sanitation')
        desc = data.get('description', 'Civic issue reported')
        
        try:
            lat = float(data.get('latitude', 28.6139))
            lon = float(data.get('longitude', 77.2090))
        except (ValueError, TypeError):
            lat, lon = 28.6139, 77.2090

        # Automatic SLA and Department Assignment
        dept_info = DEPT_RULES.get(category, {'dept': 'Sanitation & Waste Management', 'sla_hours': 24})
        deadline = (datetime.now() + timedelta(hours=dept_info['sla_hours'])).strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute('''
            INSERT INTO complaints (
                citizen_name, phone, category, description, 
                latitude, longitude, status, assigned_dept, deadline
            )
            VALUES (?, ?, ?, ?, ?, ?, 'IN_PROGRESS', ?, ?)
        ''', (name, phone, category, desc, lat, lon, dept_info['dept'], deadline))
        
        complaint_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return jsonify({
            "status": "success",
            "message": "Complaint logged to central municipal database",
            "complaint_id": complaint_id
        }), 201

# ----------------- AUTHORITY & DEPARTMENT ROUTES ----------------- #

@app.route('/api/auth/verify', methods=['POST'])
def verify_authority():
    """Validates password passkeys entered by officials"""
    data = request.get_json(silent=True) or {}
    code = data.get('access_code', '')

    if code == GOVT_ACCESS_CODE:
        return jsonify({"authorized": True, "role": "Govt Authority"}), 200
    elif code in DEPT_ACCOUNTS.values():
        return jsonify({"authorized": True, "role": "Department Field Worker"}), 200
    else:
        return jsonify({"authorized": False, "error": "Invalid clearance passkey"}), 401

@app.route('/api/complaints/<int:complaint_id>/assign', methods=['POST'])
def reassign_department(complaint_id):
    """Allows municipal authority to reassign an incident to a specific department"""
    data = request.get_json(silent=True) or {}
    new_dept = data.get('target_department')

    if not new_dept:
        return jsonify({"error": "Target department is required"}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE complaints 
        SET assigned_dept = ? 
        WHERE id = ?
    ''', (new_dept, complaint_id))
    conn.commit()
    conn.close()

    return jsonify({"status": "updated", "id": complaint_id, "assigned_dept": new_dept}), 200

@app.route('/api/complaints/<int:complaint_id>/status', methods=['POST'])
def update_status(complaint_id):
    """Updates complaint resolution status (e.g., FULFILLED, ESCALATED, FAKE_REPORT)"""
    data = request.get_json(silent=True) or {}
    new_status = data.get('status', 'FULFILLED')

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE complaints 
        SET status = ? 
        WHERE id = ?
    ''', (new_status, complaint_id))
    conn.commit()
    conn.close()

    return jsonify({"status": "updated", "id": complaint_id, "new_status": new_status}), 200

# ----------------- APPLICATION ENTRYPOINT ----------------- #

if __name__ == '__main__':
    # Binds to 0.0.0.0 and dynamically reads Render's port environment variable
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)