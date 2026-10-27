import sqlite3

DB_NAME = "civic_pulse.db"

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # 1. Citizen Complaints & Department Routing
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            citizen_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            category TEXT NOT NULL,          -- Roads, Sanitation, Electricity, Water
            description TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            assigned_dept TEXT NOT NULL,
            status TEXT DEFAULT 'OPEN',     -- OPEN, IN_PROGRESS, RESOLVED, DISPUTED, ESCALATED
            deadline TEXT NOT NULL,
            resolution_notes TEXT,
            parent_id INTEGER DEFAULT NULL, -- Linked parent if flagged as duplicate
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 2. Escalations & Audit Trail (SLA breaches & False closures)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS escalations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            escalated_to TEXT NOT NULL,
            status TEXT DEFAULT 'ACTIVE',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (complaint_id) REFERENCES complaints (id)
        )
    ''')

    conn.commit()
    conn.close()
    print("Database initialized successfully!")

if __name__ == '__main__':
    init_db()