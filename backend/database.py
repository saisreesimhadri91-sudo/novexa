import sqlite3
import json
import math
import os
from datetime import datetime, timedelta, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "nivora.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Base Reference & User Entities
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS localities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        zone_code TEXT NOT NULL UNIQUE,
        center_lat REAL NOT NULL,
        center_lng REAL NOT NULL,
        pipeline_grid TEXT NOT NULL,
        supervisor_name TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        default_severity TEXT NOT NULL,
        sla_hours INTEGER NOT NULL,
        icon TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT NOT NULL UNIQUE,
        email TEXT,
        role TEXT NOT NULL CHECK(role IN ('resident', 'technician', 'admin')),
        locality_id INTEGER,
        privacy_opt_in INTEGER DEFAULT 1,
        created_at TEXT NOT NULL,
        FOREIGN KEY (locality_id) REFERENCES localities(id)
    );

    -- 2. Teams (Service Crews & Emergency Units)
    CREATE TABLE IF NOT EXISTS teams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        specialization TEXT NOT NULL,
        locality_id INTEGER NOT NULL,
        lead_technician_id INTEGER,
        is_active INTEGER DEFAULT 1,
        created_at TEXT NOT NULL,
        FOREIGN KEY (locality_id) REFERENCES localities(id),
        FOREIGN KEY (lead_technician_id) REFERENCES users(id)
    );

    -- 3. Legacy Issue Clusters (Preserved for compatibility)
    CREATE TABLE IF NOT EXISTS issue_clusters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cluster_code TEXT NOT NULL UNIQUE,
        locality_id INTEGER NOT NULL,
        category_id INTEGER NOT NULL,
        center_lat REAL NOT NULL,
        center_lng REAL NOT NULL,
        radius_meters REAL DEFAULT 250.0,
        complaint_count INTEGER DEFAULT 1,
        status TEXT NOT NULL CHECK(status IN ('active', 'investigating', 'resolved')),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (locality_id) REFERENCES localities(id),
        FOREIGN KEY (category_id) REFERENCES categories(id)
    );

    -- 4. Complaints (Resident Reports)
    -- Stores creation time (created_at) and occurrence time (incident_time) separately
    CREATE TABLE IF NOT EXISTS complaints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_number TEXT NOT NULL UNIQUE,
        resident_id INTEGER,
        locality_id INTEGER NOT NULL,
        category_id INTEGER NOT NULL,
        description TEXT NOT NULL,
        incident_time TEXT,
        lat REAL NOT NULL,
        lng REAL NOT NULL,
        address_landmark TEXT NOT NULL,
        house_number TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('submitted', 'clustered', 'associated', 'assigned', 'in_progress', 'resolved', 'closed')),
        priority TEXT NOT NULL CHECK(priority IN ('low', 'medium', 'high', 'critical')),
        escalated INTEGER DEFAULT 0,
        escalation_reason TEXT,
        cluster_id INTEGER,
        created_at TEXT NOT NULL,
        resolved_at TEXT,
        FOREIGN KEY (resident_id) REFERENCES users(id),
        FOREIGN KEY (locality_id) REFERENCES localities(id),
        FOREIGN KEY (category_id) REFERENCES categories(id),
        FOREIGN KEY (cluster_id) REFERENCES issue_clusters(id)
    );

    -- 5. Master Incidents (Civic Infrastructure Failures)
    CREATE TABLE IF NOT EXISTS incidents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        incident_number TEXT NOT NULL UNIQUE,
        locality_id INTEGER NOT NULL,
        category_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        severity TEXT NOT NULL CHECK(severity IN ('low', 'medium', 'high', 'critical')),
        status TEXT NOT NULL CHECK(status IN ('detected', 'investigating', 'action_required', 'in_progress', 'resolved', 'closed')),
        center_lat REAL NOT NULL,
        center_lng REAL NOT NULL,
        radius_meters REAL DEFAULT 250.0,
        first_observed_at TEXT,
        created_at TEXT NOT NULL,
        resolved_at TEXT,
        FOREIGN KEY (locality_id) REFERENCES localities(id),
        FOREIGN KEY (category_id) REFERENCES categories(id)
    );

    -- 6. Incident-Complaints Junction (Many complaints to one incident, preserving original reports)
    CREATE TABLE IF NOT EXISTS incident_complaints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        incident_id INTEGER NOT NULL,
        complaint_id INTEGER NOT NULL,
        association_type TEXT NOT NULL DEFAULT 'auto_geo_cluster',
        associated_at TEXT NOT NULL,
        distance_from_center_meters REAL DEFAULT 0.0,
        FOREIGN KEY (incident_id) REFERENCES incidents(id) ON DELETE CASCADE,
        FOREIGN KEY (complaint_id) REFERENCES complaints(id) ON DELETE CASCADE,
        UNIQUE(incident_id, complaint_id)
    );

    -- 7. Tickets (Work Orders assigned to Teams/Technicians)
    CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_number TEXT NOT NULL UNIQUE,
        incident_id INTEGER,
        complaint_id INTEGER,
        locality_id INTEGER NOT NULL,
        assigned_team_id INTEGER,
        assigned_technician_id INTEGER,
        status TEXT NOT NULL CHECK(status IN ('dispatched', 'accepted', 'on_site', 'in_progress', 'blocked_escalated', 'resolved', 'closed')),
        priority TEXT NOT NULL CHECK(priority IN ('low', 'medium', 'high', 'critical')),
        sla_deadline TEXT,
        resolution_notes TEXT,
        proof_photo_url TEXT,
        created_at TEXT NOT NULL,
        dispatched_at TEXT,
        resolved_at TEXT,
        FOREIGN KEY (incident_id) REFERENCES incidents(id) ON DELETE SET NULL,
        FOREIGN KEY (complaint_id) REFERENCES complaints(id) ON DELETE SET NULL,
        FOREIGN KEY (locality_id) REFERENCES localities(id),
        FOREIGN KEY (assigned_team_id) REFERENCES teams(id),
        FOREIGN KEY (assigned_technician_id) REFERENCES users(id)
    );

    -- 8. Ticket Events (Records status transitions, reassignments & resolutions)
    CREATE TABLE IF NOT EXISTS ticket_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id INTEGER NOT NULL,
        event_type TEXT NOT NULL CHECK(event_type IN ('created', 'assigned', 'reassigned', 'status_changed', 'escalated', 'note_added', 'resolved', 'closed')),
        from_status TEXT,
        to_status TEXT,
        from_team_id INTEGER,
        to_team_id INTEGER,
        performed_by_user_id INTEGER,
        notes TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
        FOREIGN KEY (from_team_id) REFERENCES teams(id),
        FOREIGN KEY (to_team_id) REFERENCES teams(id),
        FOREIGN KEY (performed_by_user_id) REFERENCES users(id)
    );

    -- 9. Legacy Service Assignments & Feedback (Preserved for compatibility)
    CREATE TABLE IF NOT EXISTS service_assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        complaint_id INTEGER NOT NULL UNIQUE,
        technician_id INTEGER NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('dispatched', 'on_site', 'completed')),
        notes TEXT,
        proof_photo_url TEXT,
        assigned_at TEXT NOT NULL,
        completed_at TEXT,
        FOREIGN KEY (complaint_id) REFERENCES complaints(id),
        FOREIGN KEY (technician_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        complaint_id INTEGER NOT NULL UNIQUE,
        rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
        comment TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (complaint_id) REFERENCES complaints(id)
    );

    -- 10. Audit Logs
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_name TEXT NOT NULL,
        action TEXT NOT NULL,
        details TEXT NOT NULL,
        timestamp TEXT NOT NULL
    );
    """)

    # Column migrations on existing complaints table if needed
    cursor.execute("PRAGMA table_info(complaints)")
    cols = [row["name"] for row in cursor.fetchall()]
    if "incident_time" not in cols:
        cursor.execute("ALTER TABLE complaints ADD COLUMN incident_time TEXT")
    if "escalated" not in cols:
        cursor.execute("ALTER TABLE complaints ADD COLUMN escalated INTEGER DEFAULT 0")
    if "escalation_reason" not in cols:
        cursor.execute("ALTER TABLE complaints ADD COLUMN escalation_reason TEXT")

    # Create Indexes (Relational & Geospatial)
    cursor.executescript("""
    CREATE INDEX IF NOT EXISTS idx_complaints_locality ON complaints(locality_id);
    CREATE INDEX IF NOT EXISTS idx_complaints_created ON complaints(created_at);
    CREATE INDEX IF NOT EXISTS idx_complaints_occurred ON complaints(incident_time);
    CREATE INDEX IF NOT EXISTS idx_complaints_status ON complaints(status);
    CREATE INDEX IF NOT EXISTS idx_complaints_coords ON complaints(lat, lng);
    CREATE INDEX IF NOT EXISTS idx_incidents_locality ON incidents(locality_id);
    CREATE INDEX IF NOT EXISTS idx_incidents_coords ON incidents(center_lat, center_lng);
    CREATE INDEX IF NOT EXISTS idx_inc_comp_incident ON incident_complaints(incident_id);
    CREATE INDEX IF NOT EXISTS idx_inc_comp_complaint ON incident_complaints(complaint_id);
    CREATE INDEX IF NOT EXISTS idx_tickets_incident ON tickets(incident_id);
    CREATE INDEX IF NOT EXISTS idx_tickets_team ON tickets(assigned_team_id);
    CREATE INDEX IF NOT EXISTS idx_ticket_events_ticket ON ticket_events(ticket_id);
    
    -- Locality Geographic Summary View (GIS analysis without exposing private citizen addresses)
    CREATE VIEW IF NOT EXISTS locality_geographic_summary AS
    SELECT 
        l.id AS locality_id,
        l.name AS locality_name,
        l.zone_code,
        l.center_lat,
        l.center_lng,
        l.pipeline_grid,
        l.supervisor_name,
        COUNT(DISTINCT c.id) AS total_complaints,
        COUNT(DISTINCT CASE WHEN c.status IN ('submitted', 'clustered', 'associated', 'assigned', 'in_progress') THEN c.id END) AS active_complaints,
        COUNT(DISTINCT i.id) AS active_incidents,
        COUNT(DISTINCT CASE WHEN cat.name = 'Pipeline Leak / Burst' THEN c.id END) AS leak_complaints_count,
        COUNT(DISTINCT CASE WHEN cat.name = 'Water Contamination' THEN c.id END) AS contamination_complaints_count
    FROM localities l
    LEFT JOIN complaints c ON l.id = c.locality_id
    LEFT JOIN categories cat ON c.category_id = cat.id
    LEFT JOIN incidents i ON l.id = i.locality_id AND i.status IN ('detected', 'investigating', 'action_required', 'in_progress')
    GROUP BY l.id, l.name, l.zone_code, l.center_lat, l.center_lng, l.pipeline_grid, l.supervisor_name;
    """)

    conn.commit()
    seed_if_empty(conn)
    conn.close()

def seed_if_empty(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM localities")
    if cursor.fetchone()[0] > 0:
        # Check if teams need seeding
        cursor.execute("SELECT COUNT(*) FROM teams")
        if cursor.fetchone()[0] == 0:
            seed_relational_entities(conn)
        return

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    # 1. Localities
    localities = [
        ("North Ward - Sector 4", "NW-04", 28.6280, 77.2080, "Grid Alpha-North (Main 400mm)", "Rajendra Prasad"),
        ("East Ward - Lakeview", "EW-02", 28.6335, 77.2250, "Grid Beta-East (Lake Line)", "Sunita Rao"),
        ("South Ward - Green Valley", "SW-09", 28.6140, 77.2120, "Grid Gamma-South (Highlands)", "Col. Arvind Mehta"),
        ("West Ward - Industrial Belt", "WW-05", 28.6210, 77.1950, "Grid Delta-West (Industrial Feeder)", "Vikram Solanki")
    ]
    cursor.executemany("""
    INSERT INTO localities (name, zone_code, center_lat, center_lng, pipeline_grid, supervisor_name)
    VALUES (?, ?, ?, ?, ?, ?)
    """, localities)

    # 2. Categories
    categories = [
        ("Pipeline Leak / Burst", "critical", 6, "droplets"),
        ("Water Contamination", "critical", 8, "alert-triangle"),
        ("No Water Supply", "high", 12, "slash"),
        ("Low Water Pressure", "medium", 24, "gauge"),
        ("Faulty Valve / Meter", "low", 48, "wrench")
    ]
    cursor.executemany("""
    INSERT INTO categories (name, default_severity, sla_hours, icon)
    VALUES (?, ?, ?, ?)
    """, categories)

    # 3. Users
    users = [
        ("Priya Sharma", "+91 9876543210", "priya.sharma@example.com", "resident", 1, 1, (now - timedelta(days=20)).isoformat()),
        ("Rahul Verma", "+91 9811223344", "rahul.verma@example.com", "resident", 1, 1, (now - timedelta(days=15)).isoformat()),
        ("Ananya Iyer", "+91 9822334455", "ananya.iyer@example.com", "resident", 1, 1, (now - timedelta(days=10)).isoformat()),
        ("Vikram Patel", "+91 9833445566", "vikram.patel@example.com", "resident", 2, 1, (now - timedelta(days=5)).isoformat()),
        ("Meera Sen", "+91 9844556677", "meera.sen@example.com", "resident", 3, 1, (now - timedelta(days=3)).isoformat()),
        # Technicians
        ("Rajesh Kumar", "+91 9700112233", "rajesh.k@waterworks.gov", "technician", 1, 0, (now - timedelta(days=60)).isoformat()),
        ("Suresh Yadav", "+91 9711223344", "suresh.y@waterworks.gov", "technician", 2, 0, (now - timedelta(days=50)).isoformat()),
        ("Amit Singh", "+91 9722334455", "amit.s@waterworks.gov", "technician", 3, 0, (now - timedelta(days=40)).isoformat()),
        # Admin
        ("City Water Commissioner (Central Admin)", "+91 9999900000", "admin@nivora.gov", "admin", None, 0, (now - timedelta(days=100)).isoformat())
    ]
    cursor.executemany("""
    INSERT INTO users (name, phone, email, role, locality_id, privacy_opt_in, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, users)

    # 4. Issue Cluster in North Ward (Active main line leak detected from multiple residents)
    cursor.execute("""
    INSERT INTO issue_clusters (cluster_code, locality_id, category_id, center_lat, center_lng, radius_meters, complaint_count, status, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "CLS-NW-2026-081",
        1,  # North Ward
        1,  # Pipeline Leak / Burst
        28.6282,
        77.2084,
        250.0,
        3,
        "active",
        (now - timedelta(hours=3, minutes=45)).isoformat(),
        (now - timedelta(hours=1, minutes=10)).isoformat()
    ))
    cluster_id = cursor.lastrowid

    # 5. Complaints
    complaints = [
        ("TKT-2026-1001", 1, 1, 1, "Severe gushing water near main avenue circle; pressure has vanished.", (now - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M"), 28.6282, 77.2083, "Opposite Metro Gate 2", "Flat 402, Block B", "clustered", "critical", 0, None, cluster_id, (now - timedelta(hours=3, minutes=45)).isoformat(), None),
        ("TKT-2026-1002", 2, 1, 1, "Major water fountain in front of Community Hall. Road is flooding.", (now - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M"), 28.6284, 77.2086, "Near Community Center", "House 12, Lane 3", "clustered", "critical", 0, None, cluster_id, (now - timedelta(hours=2, minutes=30)).isoformat(), None),
        ("TKT-2026-1003", 3, 1, 1, "Water flow completely cut off since 2 PM; pipeline fissure spotted.", (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M"), 28.6281, 77.2081, "Behind Apex Pharmacy", "Apartment 101", "assigned", "critical", 0, None, cluster_id, (now - timedelta(hours=1, minutes=10)).isoformat(), None),
        ("TKT-2026-0988", 4, 2, 2, "Water coming from tap has brownish yellow sediment and foul odor.", (now - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M"), 28.6338, 77.2255, "Lakeview Circle", "House 88, 4th Cross", "in_progress", "critical", 0, None, None, (now - timedelta(hours=5)).isoformat(), None),
        ("TKT-2026-0972", 5, 3, 4, "Extremely low pressure for past 3 days. Takes 2 hours to fill tank.", (now - timedelta(days=2, hours=3)).strftime("%Y-%m-%d %H:%M"), 28.6145, 77.2125, "Valley Garden Park", "Villa 24-B", "resolved", "medium", 0, None, None, (now - timedelta(days=2)).isoformat(), (now - timedelta(days=1, hours=4)).isoformat())
    ]
    cursor.executemany("""
    INSERT INTO complaints (ticket_number, resident_id, locality_id, category_id, description, incident_time, lat, lng, address_landmark, house_number, status, priority, escalated, escalation_reason, cluster_id, created_at, resolved_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, complaints)

    # 6. Service Assignments
    assignments = [
        (3, 6, "dispatched", "Dispatched to inspect main 400mm feeder junction under CLS-NW-2026-081.", "https://images.unsplash.com/photo-1584622650111-993a426fbf0a?auto=format&fit=crop&w=400&q=80", (now - timedelta(hours=1)).isoformat(), None),
        (4, 7, "on_site", "Collecting water sample from filtration point; line isolation requested.", None, (now - timedelta(hours=4)).isoformat(), None),
        (5, 8, "completed", "Replaced worn-out booster pressure regulator valve. Pressure restored to 3.2 bar.", "https://images.unsplash.com/photo-1621905251189-08b45d6a269e?auto=format&fit=crop&w=400&q=80", (now - timedelta(days=1, hours=8)).isoformat(), (now - timedelta(days=1, hours=4)).isoformat())
    ]
    cursor.executemany("""
    INSERT INTO service_assignments (complaint_id, technician_id, status, notes, proof_photo_url, assigned_at, completed_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, assignments)

    # 7. Feedback
    cursor.execute("""
    INSERT INTO feedback (complaint_id, rating, comment, created_at)
    VALUES (?, ?, ?, ?)
    """, (5, 5, "Technician Amit was prompt and solved the low pressure issue effectively. Great job!", (now - timedelta(days=1)).isoformat()))

    # 8. Audit Logs
    audit_entries = [
        ("System Automated Engine", "DETECT_CLUSTER", "Grouped 3 complaints into Incident Cluster CLS-NW-2026-081 within 185m radius.", (now - timedelta(hours=1, minutes=10)).isoformat()),
        ("City Water Commissioner", "DISPATCH_TEAM", "Assigned Lead Technician Rajesh Kumar to Master Cluster CLS-NW-2026-081.", (now - timedelta(hours=1)).isoformat()),
        ("Privacy Enforcement", "MASK_PII", "Masked resident phone numbers and flat IDs from field technician views.", (now - timedelta(hours=1)).isoformat())
    ]
    cursor.executemany("""
    INSERT INTO audit_logs (user_name, action, details, timestamp)
    VALUES (?, ?, ?, ?)
    """, audit_entries)

    conn.commit()
    seed_relational_entities(conn)

def seed_relational_entities(conn):
    cursor = conn.cursor()
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    # 1. Teams
    teams_data = [
        ("North Ward Rapid Repair Crew", "Heavy Pipe Burst & Excavation", 1, 6, 1, (now - timedelta(days=30)).isoformat()),
        ("East Ward Water Quality Division", "Contamination & Chemical Analysis", 2, 7, 1, (now - timedelta(days=30)).isoformat()),
        ("South Ward Pressure Management Unit", "Booster Valves & Regulators", 3, 8, 1, (now - timedelta(days=30)).isoformat())
    ]
    cursor.executemany("""
    INSERT OR IGNORE INTO teams (name, specialization, locality_id, lead_technician_id, is_active, created_at)
    VALUES (?, ?, ?, ?, ?, ?)
    """, teams_data)

    # 2. Master Incident in North Ward
    cursor.execute("SELECT id FROM incidents WHERE incident_number = 'INC-NW-2026-081'")
    inc_row = cursor.fetchone()
    if not inc_row:
        cursor.execute("""
        INSERT INTO incidents (incident_number, locality_id, category_id, title, description, severity, status, center_lat, center_lng, radius_meters, first_observed_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "INC-NW-2026-081",
            1, # North Ward
            1, # Pipeline Leak / Burst
            "Main 400mm Feeder Line Rupture (Sector 4)",
            "Multiple reports of road flooding and water loss along Metro Gate 2 avenue.",
            "critical",
            "in_progress",
            28.6282, 77.2084,
            250.0,
            (now - timedelta(hours=4)).isoformat(),
            (now - timedelta(hours=3, minutes=45)).isoformat()
        ))
        incident_id = cursor.lastrowid
    else:
        incident_id = inc_row[0]

    # 3. Associate Complaints to the Incident (Preserving original complaints)
    complaint_ids = [1, 2, 3] # The 3 North Ward complaints
    for cid in complaint_ids:
        cursor.execute("""
        INSERT OR IGNORE INTO incident_complaints (incident_id, complaint_id, association_type, associated_at, distance_from_center_meters)
        VALUES (?, ?, 'auto_geo_cluster', ?, ?)
        """, (incident_id, cid, (now - timedelta(hours=2)).isoformat(), 45.0))

    # 4. Master Ticket (Work Order) for the Incident
    cursor.execute("SELECT id FROM tickets WHERE ticket_number = 'WO-2026-0042'")
    tkt_row = cursor.fetchone()
    if not tkt_row:
        cursor.execute("""
        INSERT INTO tickets (ticket_number, incident_id, complaint_id, locality_id, assigned_team_id, assigned_technician_id, status, priority, sla_deadline, resolution_notes, proof_photo_url, created_at, dispatched_at)
        VALUES (?, ?, NULL, 1, 1, 6, 'in_progress', 'critical', ?, 'Collar isolation and clamp replacement underway.', 'https://images.unsplash.com/photo-1584622650111-993a426fbf0a?auto=format&fit=crop&w=400&q=80', ?, ?)
        """, (
            "WO-2026-0042",
            incident_id,
            (now + timedelta(hours=3)).isoformat(),
            (now - timedelta(hours=2)).isoformat(),
            (now - timedelta(hours=1, minutes=30)).isoformat()
        ))
        ticket_id = cursor.lastrowid

        # 5. Ticket Events (Lifecycle Audit)
        events = [
            (ticket_id, "created", None, "dispatched", None, 1, 9, "Ticket generated from Master Incident INC-NW-2026-081.", (now - timedelta(hours=2)).isoformat()),
            (ticket_id, "assigned", "dispatched", "dispatched", None, 1, 9, "Assigned to North Ward Rapid Repair Crew (Lead: Rajesh Kumar).", (now - timedelta(hours=1, minutes=50)).isoformat()),
            (ticket_id, "status_changed", "dispatched", "on_site", 1, 1, 6, "Technician arrived on site with 400mm collar replacement kit.", (now - timedelta(hours=1)).isoformat()),
            (ticket_id, "status_changed", "on_site", "in_progress", 1, 1, 6, "Valve isolated; beginning pipe excavation.", (now - timedelta(minutes=30)).isoformat())
        ]
        cursor.executemany("""
        INSERT INTO ticket_events (ticket_id, event_type, from_status, to_status, from_team_id, to_team_id, performed_by_user_id, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, events)

    conn.commit()

if __name__ == "__main__":
    init_db()
    print("NIVORA Database successfully initialized with all 9 core entities at:", DB_PATH)
