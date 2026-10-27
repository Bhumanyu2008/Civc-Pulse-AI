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

@app.route('/api/complaints', methods=['GET', 'POST'])
def manage_complaints():
    conn = get_db()
    cursor = conn.cursor()

    # 1. Reading complaints (for Govt Authority and citizen tracking)
    if request.method == 'GET':
        cursor.execute("SELECT * FROM complaints ORDER BY id DESC")
        rows = cursor.fetchall()
        conn.close()
        # Return all complaints as JSON list
        return jsonify([dict(r) for r in rows])

    # 2. Submitting a new complaint (from Public Portal form)
    if request.method == 'POST':
        data = request.get_json() or {}
        name = data.get('citizen_name', 'Anonymous Citizen')
        phone = data.get('phone', '0000000000')
        category = data.get('category', 'Roads')
        desc = data.get('description', '')
        lat = float(data.get('latitude', 28.6139))
        lon = float(data.get('longitude', 77.2090))

        dept_info = DEPT_RULES.get(category, {'dept': 'General Administration', 'sla_hours': 48})
        deadline = (datetime.now() + timedelta(hours=dept_info['sla_hours'])).strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute('''
            INSERT INTO complaints (citizen_name, phone, category, description, latitude, longitude, assigned_dept, deadline)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, phone, category, desc, lat, lon, dept_info['dept'], deadline))
        
        complaint_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return jsonify({"status": "success", "complaint_id": complaint_id}), 201