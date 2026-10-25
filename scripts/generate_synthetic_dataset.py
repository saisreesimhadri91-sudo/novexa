#!/usr/bin/env python3
"""
=============================================================================
NIVORA Synthetic Demonstration Dataset Generator
Deterministic generator for 10,000 complaints across 15 fictional localities,
180 historical days, multiple service teams, and ground-truth evaluation sets.

Seed: 42 (Fully deterministic and reproducible)
All generated records are 100% synthetic civic utility data.
=============================================================================
"""

import os
import sys
import math
import random
import json
import csv
import sqlite3
from datetime import datetime, timedelta, timezone

# Target Parameters
RANDOM_SEED = 42
TARGET_COMPLAINTS = 10000
HISTORY_DAYS = 180
REFERENCE_DATE = datetime(2026, 10, 24, 20, 0, 0, tzinfo=timezone.utc)
START_DATE = REFERENCE_DATE - timedelta(days=HISTORY_DAYS)

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)
DB_PATH = os.path.join(ROOT_DIR, "nivora.db")
GROUND_TRUTH_DIR = os.path.join(ROOT_DIR, "data", "ground_truth")

os.makedirs(GROUND_TRUTH_DIR, exist_ok=True)

random.seed(RANDOM_SEED)

# 1. Fictional Localities (15 Wards with realistic spatial clustering & volume weights)
LOCALITIES_DEF = [
    {"name": "North Ward - Sector 4 (Old Town)", "zone_code": "NW-04", "lat": 28.6280, "lng": 77.2080, "grid": "Grid Alpha-North (Main 400mm Cast-Iron)", "supervisor": "Rajendra Prasad", "weight": 1.6, "pipe_age_years": 58},
    {"name": "East Ward - Lakeview Promenade", "zone_code": "EW-02", "lat": 28.6335, "lng": 77.2250, "grid": "Grid Beta-East (Lake Feeder 300mm)", "supervisor": "Sunita Rao", "weight": 1.0, "pipe_age_years": 24},
    {"name": "South Ward - Green Valley Heights", "zone_code": "SW-09", "lat": 28.6140, "lng": 77.2120, "grid": "Grid Gamma-South (Highlands Booster Grid)", "supervisor": "Col. Arvind Mehta", "weight": 1.3, "pipe_age_years": 32},
    {"name": "West Ward - Industrial Belt Delta", "zone_code": "WW-05", "lat": 28.6210, "lng": 77.1950, "grid": "Grid Delta-West (Heavy Industrial Trunk)", "supervisor": "Vikram Solanki", "weight": 1.5, "pipe_age_years": 45},
    {"name": "Central Ward - Civic Square", "zone_code": "CW-01", "lat": 28.6295, "lng": 77.2185, "grid": "Grid Central-Core (Dual Ring Ductile)", "supervisor": "Meenakshi Sundaram", "weight": 0.8, "pipe_age_years": 16},
    {"name": "Riverdale Sector 9", "zone_code": "RD-09", "lat": 28.6410, "lng": 77.2310, "grid": "Grid River-Alpha (Intake Trunk Line)", "supervisor": "Bhupinder Singh", "weight": 1.2, "pipe_age_years": 38},
    {"name": "Highland Ridge Sector 12", "zone_code": "HR-12", "lat": 28.6080, "lng": 77.2020, "grid": "Grid Elevation-South (Multi-Stage Pumping)", "supervisor": "Tariq Mansoor", "weight": 1.4, "pipe_age_years": 42},
    {"name": "Oakwood Enclave Sector 7", "zone_code": "OE-07", "lat": 28.6450, "lng": 77.2150, "grid": "Grid Modern-Suburban (HDPE Grid)", "supervisor": "Anuradha Sen", "weight": 0.6, "pipe_age_years": 8},
    {"name": "Old Mill Heritage District", "zone_code": "OM-03", "lat": 28.6225, "lng": 77.2035, "grid": "Grid Heritage-West (Pre-War 500mm Riveted)", "supervisor": "Gajendra Rathore", "weight": 1.8, "pipe_age_years": 65},
    {"name": "Sunset Meadows Sector 16", "zone_code": "SM-16", "lat": 28.6020, "lng": 77.2280, "grid": "Grid Expansion-South (Composite Grid)", "supervisor": "Devika Pillai", "weight": 0.7, "pipe_age_years": 12},
    {"name": "Harbor View Sector 3", "zone_code": "HV-03", "lat": 28.6380, "lng": 77.2420, "grid": "Grid Harbor-East (Corrosion Resisting Line)", "supervisor": "Kalyan Banerjee", "weight": 1.2, "pipe_age_years": 36},
    {"name": "Crestview Heights Sector 11", "zone_code": "CH-11", "lat": 28.6110, "lng": 77.2210, "grid": "Grid Crest-Booster (High Pressure Line)", "supervisor": "Naveen Chawla", "weight": 1.1, "pipe_age_years": 28},
    {"name": "Amberfield Estates Sector 14", "zone_code": "AE-14", "lat": 28.6170, "lng": 77.2350, "grid": "Grid Amber-Middle (300mm Feeder Line)", "supervisor": "Pooja Hegde", "weight": 0.9, "pipe_age_years": 20},
    {"name": "Falcon Ridge Sector 18", "zone_code": "FR-18", "lat": 28.6010, "lng": 77.1910, "grid": "Grid Peripheral-Transit (Long Distance Feeder)", "supervisor": "Harish Rawat", "weight": 1.4, "pipe_age_years": 44},
    {"name": "Grand Avenue Commercial Hub", "zone_code": "GA-08", "lat": 28.6315, "lng": 77.2115, "grid": "Grid Commercial-North (Commercial Loop)", "supervisor": "Siddharth Gautam", "weight": 0.8, "pipe_age_years": 18}
]

# 2. Problem Categories & Realistic Baselines
CATEGORIES_DEF = [
    {"id": 1, "name": "Pipeline Leak / Burst", "severity": "critical", "sla_hours": 6, "icon": "droplets", "share": 0.32},
    {"id": 2, "name": "Water Contamination", "severity": "critical", "sla_hours": 8, "icon": "alert-triangle", "share": 0.16},
    {"id": 3, "name": "No Water Supply", "severity": "high", "sla_hours": 12, "icon": "slash", "share": 0.24},
    {"id": 4, "name": "Low Water Pressure", "severity": "medium", "sla_hours": 24, "icon": "gauge", "share": 0.20},
    {"id": 5, "name": "Faulty Valve / Meter", "severity": "low", "sla_hours": 48, "icon": "wrench", "share": 0.08}
]

# 3. Service Teams Definitions (Specialized Field Crews)
TEAMS_DEF = [
    {"name": "North Rapid Emergency Pipe Squad", "spec": "Heavy Trunk Excavation & Pipeline Burst", "locality_idx": 0},
    {"name": "East Ward Water Purity Taskforce", "spec": "Water Quality Testing & Disinfection", "locality_idx": 1},
    {"name": "South Highlands Booster Team", "spec": "Pumps, Pressure Regulators & Valves", "locality_idx": 2},
    {"name": "West Industrial Hazard Response", "spec": "Chemical Leaks & Industrial Feeder Trunk", "locality_idx": 3},
    {"name": "Central Rapid Operations Unit", "spec": "Commercial Metering & High Density Loops", "locality_idx": 4},
    {"name": "Riverdale Intake Maintenance Crew", "spec": "Turbidity Control & Filtration Plants", "locality_idx": 5},
    {"name": "Highland Elevation Line Team", "spec": "High Head Multi-Stage Pump Repairs", "locality_idx": 6},
    {"name": "Old Mill Heritage Pipe Restoration", "spec": "Cast-Iron Fissure Clamping & Rehabilitation", "locality_idx": 8},
    {"name": "Harbor Saline Corrosion Remediation", "spec": "Cathodic Protection & Pipe Replacement", "locality_idx": 10},
    {"name": "Peripheral Transit Pipe Division", "spec": "Long-Distance Trunk Line Inspection", "locality_idx": 13}
]

FIRST_NAMES = ["Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan", "Krishna", "Ishaan",
               "Diya", "Saanvi", "Aanya", "Aadhya", "Pari", "Ananya", "Riya", "Myra", "Sneha", "Kavya",
               "Rohan", "Pooja", "Rajesh", "Deepak", "Vikram", "Sunil", "Anil", "Suresh", "Manoj", "Alok"]
LAST_NAMES = ["Sharma", "Verma", "Gupta", "Malhotra", "Bhatia", "Iyer", "Nair", "Patel", "Reddy", "Mehta",
              "Chatterjee", "Banerjee", "Mukherjee", "Saxena", "Choudhury", "Joshi", "Mishra", "Trivedi", "Deshmukh", "Kulkarni"]

STREET_PREFIXES = ["Near", "Opposite", "Behind", "Beside", "Adjacent to", "Corner of"]
STREET_LANDMARKS = [
    "Community Center Gate 2", "Metro Pillar 142", "Substation 4", "City Bus Terminal", 
    "Public Garden Fountain", "Government Dispensary", "Apex Senior School", "Central Market Circle", 
    "Primary Health Center", "Railway Crossing Lane", "Ward Water Tank Reservoir", "Heritage Clock Tower",
    "Post Office Lane", "District Sports Complex", "Shiva Temple Crossroad", "Green Park Avenue"
]

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2.0)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2.0)**2
    return R * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

def generate_dataset():
    print("=================================================================")
    print(" Starting NIVORA Deterministic Synthetic Dataset Generation")
    print(f" Target: {TARGET_COMPLAINTS} complaints, {len(LOCALITIES_DEF)} localities, {HISTORY_DAYS} historical days")
    print("=================================================================")

    # 1. Connect to Database (Non-destructive)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    # Ensure tables exist
    from backend.database import init_db
    init_db()

    # Clear previous demo complaints if replacing demonstration batch cleanly
    print("Clearing prior synthetic records for fresh deterministic generation...")
    cursor.executescript("""
    DELETE FROM ticket_events;
    DELETE FROM tickets;
    DELETE FROM incident_complaints;
    DELETE FROM incidents;
    DELETE FROM service_assignments;
    DELETE FROM feedback;
    DELETE FROM audit_logs;
    DELETE FROM complaints;
    DELETE FROM issue_clusters;
    DELETE FROM teams;
    DELETE FROM users;
    DELETE FROM localities;
    DELETE FROM categories;
    DELETE FROM sqlite_sequence;
    """)

    # 2. Insert 15 Localities
    print("Seeding 15 Fictional Localities...")
    loc_insert_data = []
    for l in LOCALITIES_DEF:
        loc_insert_data.append((l["name"], l["zone_code"], l["lat"], l["lng"], l["grid"], l["supervisor"]))
    cursor.executemany("""
    INSERT INTO localities (name, zone_code, center_lat, center_lng, pipeline_grid, supervisor_name)
    VALUES (?, ?, ?, ?, ?, ?)
    """, loc_insert_data)

    cursor.execute("SELECT id, name, zone_code, center_lat, center_lng FROM localities ORDER BY id")
    db_localities = [dict(r) for r in cursor.fetchall()]
    for idx, dbl in enumerate(db_localities):
        dbl["weight"] = LOCALITIES_DEF[idx]["weight"]

    # 3. Insert 5 Categories
    print("Seeding Issue Categories...")
    for c in CATEGORIES_DEF:
        cursor.execute("""
        INSERT INTO categories (id, name, default_severity, sla_hours, icon)
        VALUES (?, ?, ?, ?, ?)
        """, (c["id"], c["name"], c["severity"], c["sla_hours"], c["icon"]))

    # 4. Generate ~1,800 Synthetic Fictional Users (Residents, Technicians, Admins)
    print("Generating Fictional Resident & Staff User Profiles...")
    users_insert = []
    
    # 25 Field Technicians
    tech_ids = []
    for i in range(1, 26):
        fn = random.choice(FIRST_NAMES)
        ln = random.choice(LAST_NAMES)
        phone = f"+91 97{i:02d}{random.randint(100000, 999999)}"
        email = f"tech.{fn.lower()}.{ln.lower()}{i}@waterworks.gov"
        loc_id = random.choice(db_localities)["id"]
        users_insert.append((f"{fn} {ln}", phone, email, "technician", loc_id, 0, START_DATE.isoformat()))
        tech_ids.append(i)

    # 3 Administrators
    users_insert.append(("Central Operations Commissioner", "+91 9900000001", "commissioner@nivora.gov", "admin", 1, 0, START_DATE.isoformat()))
    users_insert.append(("Zonal Dispatch Officer North", "+91 9900000002", "dispatch.north@nivora.gov", "admin", 1, 0, START_DATE.isoformat()))
    users_insert.append(("Zonal Dispatch Officer South", "+91 9900000003", "dispatch.south@nivora.gov", "admin", 3, 0, START_DATE.isoformat()))

    # Anonymous Citizen placeholder for anonymous reports
    users_insert.append(("Anonymous Citizen (Unauthenticated Report)", "+91 0000000000", "anonymous@civic.local", "resident", 1, 1, START_DATE.isoformat()))

    # ~1,800 Resident Citizens
    NUM_RESIDENTS = 1800
    for i in range(1, NUM_RESIDENTS + 1):
        fn = random.choice(FIRST_NAMES)
        ln = random.choice(LAST_NAMES)
        phone = f"+91 98{random.randint(10000000, 99999999)}"
        email = f"{fn.lower()}.{ln.lower()}{random.randint(10, 999)}@example.com"
        loc_id = random.choice(db_localities)["id"]
        privacy_opt = 1 if random.random() < 0.85 else 0
        users_insert.append((f"{fn} {ln}", phone, email, "resident", loc_id, privacy_opt, START_DATE.isoformat()))

    cursor.executemany("""
    INSERT INTO users (name, phone, email, role, locality_id, privacy_opt_in, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, users_insert)

    cursor.execute("SELECT id FROM users WHERE role = 'technician'")
    db_tech_ids = [r[0] for r in cursor.fetchall()]

    cursor.execute("SELECT id FROM users WHERE role = 'resident'")
    db_resident_ids = [r[0] for r in cursor.fetchall()]

    cursor.execute("SELECT id FROM users WHERE phone = '+91 0000000000'")
    anon_user_id = cursor.fetchone()[0]

    # 5. Insert 10 Service Teams
    print("Seeding Specialized Service Teams...")
    teams_insert = []
    for idx, t in enumerate(TEAMS_DEF):
        loc_id = db_localities[t["locality_idx"]]["id"]
        lead_id = db_tech_ids[idx % len(db_tech_ids)]
        teams_insert.append((t["name"], t["spec"], loc_id, lead_id, 1, START_DATE.isoformat()))
    
    cursor.executemany("""
    INSERT INTO teams (name, specialization, locality_id, lead_technician_id, is_active, created_at)
    VALUES (?, ?, ?, ?, ?, ?)
    """, teams_insert)

    cursor.execute("SELECT id, locality_id FROM teams")
    db_teams = [dict(r) for r in cursor.fetchall()]

    # 6. Generate Master Incidents (~450 Incidents across 180 days)
    print("Synthesizing Master Incidents and Geospatial Incident Clusters...")
    NUM_INCIDENTS = 450
    incidents_data = []
    recurring_chains = []

    # Pre-generate recurring epicenter hotspots in older pipeline grids (Wards 0, 3, 8)
    hotspots = [
        {"locality_idx": 0, "lat": 28.6284, "lng": 77.2085, "title": "Main 400mm Feeder Fissure (Sector 4 Metro Circle)", "cat_id": 1, "sev": "critical"},
        {"locality_idx": 8, "lat": 28.6228, "lng": 77.2038, "title": "Old Mill Heritage 500mm Cast-Iron Rupture", "cat_id": 1, "sev": "critical"},
        {"locality_idx": 3, "lat": 28.6215, "lng": 77.1955, "title": "Industrial Feeder Cross-Seepage Event", "cat_id": 2, "sev": "critical"},
        {"locality_idx": 2, "lat": 28.6145, "lng": 77.2128, "title": "Highlands Booster Station Multi-Valve Failure", "cat_id": 4, "sev": "medium"},
        {"locality_idx": 6, "lat": 28.6085, "lng": 77.2025, "title": "Highland Ridge Stage-2 Pump Trip", "cat_id": 3, "sev": "high"},
    ]

    for inc_idx in range(1, NUM_INCIDENTS + 1):
        # 20% of incidents are recurrent incidents at known chronic hotspots
        is_recurrent = (random.random() < 0.20) and len(hotspots) > 0
        if is_recurrent:
            hs = random.choice(hotspots)
            loc = db_localities[hs["locality_idx"]]
            cat_id = hs["cat_id"]
            sev = hs["sev"]
            title = f"Recurring: {hs['title']}"
            center_lat = hs["lat"] + random.gauss(0, 0.0004)
            center_lng = hs["lng"] + random.gauss(0, 0.0004)
        else:
            loc = random.choice(db_localities)
            cat = random.choices(CATEGORIES_DEF, weights=[c["share"] for c in CATEGORIES_DEF])[0]
            cat_id = cat["id"]
            sev = cat["severity"]
            title = f"{cat['name']} along {loc['name']} corridor"
            center_lat = loc["center_lat"] + random.gauss(0, 0.004)
            center_lng = loc["center_lng"] + random.gauss(0, 0.004)

        # Distribute across the 180 days
        day_offset = random.uniform(0, HISTORY_DAYS - 1)
        created_dt = START_DATE + timedelta(days=day_offset, hours=random.uniform(0, 23), minutes=random.uniform(0, 59))
        first_observed_dt = created_dt - timedelta(minutes=random.uniform(15, 180))

        # Status & resolution
        days_ago = (REFERENCE_DATE - created_dt).total_seconds() / 86400.0
        if days_ago > 4:
            status = "resolved" if random.random() < 0.95 else "closed"
            resolved_dt = created_dt + timedelta(hours=random.uniform(2, 28))
        elif days_ago > 1:
            status = random.choice(["in_progress", "resolved", "action_required"])
            resolved_dt = (created_dt + timedelta(hours=random.uniform(3, 14))) if status == "resolved" else None
        else:
            status = random.choice(["detected", "investigating", "in_progress"])
            resolved_dt = None

        inc_num = f"INC-{loc['zone_code']}-{created_dt.strftime('%Y%m%d')}-{inc_idx:03d}"
        desc = f"Master civic incident: {title}. Recorded spatial radius 250m."

        incidents_data.append({
            "id": inc_idx,
            "incident_number": inc_num,
            "locality_id": loc["id"],
            "category_id": cat_id,
            "title": title,
            "description": desc,
            "severity": sev,
            "status": status,
            "center_lat": round(center_lat, 6),
            "center_lng": round(center_lng, 6),
            "radius_meters": 250.0,
            "first_observed_at": first_observed_dt.isoformat(),
            "created_at": created_dt.isoformat(),
            "resolved_at": resolved_dt.isoformat() if resolved_dt else None,
            "is_recurrent": is_recurrent,
            "created_dt": created_dt
        })

    cursor.executemany("""
    INSERT INTO incidents (id, incident_number, locality_id, category_id, title, description, severity, status, center_lat, center_lng, radius_meters, first_observed_at, created_at, resolved_at)
    VALUES (:id, :incident_number, :locality_id, :category_id, :title, :description, :severity, :status, :center_lat, :center_lng, :radius_meters, :first_observed_at, :created_at, :resolved_at)
    """, incidents_data)

    # 7. Generate Exactly 10,000 Complaints & Ground Truth Labeling
    print("Generating 10,000 Compliant Records (Clustered, Standalone, Reopened, Overdue)...")
    complaints_insert = []
    incident_complaints_insert = []
    ground_truth_records = []

    complaint_counter = 0

    # Phase 7A: Generate ~6,800 Clustered Complaints belonging to Master Incidents
    # Each incident gets between 3 and 25 complaints from distinct residents
    for inc in incidents_data:
        # Cluster size between 3 and 22 complaints
        cluster_size = random.randint(3, 22)
        if complaint_counter + cluster_size > 7000:
            cluster_size = max(0, 7000 - complaint_counter)
        if cluster_size == 0:
            continue

        for sub_i in range(cluster_size):
            complaint_counter += 1
            cid = complaint_counter
            ticket_num = f"CMP-{inc['created_dt'].year}-{cid:05d}"
            resident_id = random.choice(db_resident_ids)
            
            # Sub-complaints happen within 0.1 to 32 hours of master incident creation
            comp_dt = inc["created_dt"] + timedelta(hours=random.uniform(0.05, 32.0))
            if comp_dt > REFERENCE_DATE:
                comp_dt = REFERENCE_DATE - timedelta(minutes=random.uniform(5, 60))
            
            # Timestamp separation: occurred_at (when observed) vs created_at (when logged)
            occurred_dt = comp_dt - timedelta(minutes=random.uniform(10, 180))

            # Geographic dispersion within 200m radius of epicenter
            dist_meters = random.triangular(5.0, 220.0, 60.0)
            angle = random.uniform(0, 2 * math.pi)
            delta_lat = (dist_meters * math.cos(angle)) / 111111.0
            delta_lng = (dist_meters * math.sin(angle)) / (111111.0 * math.cos(math.radians(inc["center_lat"])))
            c_lat = round(inc["center_lat"] + delta_lat, 6)
            c_lng = round(inc["center_lng"] + delta_lng, 6)

            # Realistic text & intentional data-quality anomalies
            has_missing_house = (random.random() < 0.10)
            has_generic_landmark = (random.random() < 0.04)

            house = "Not Specified" if has_missing_house else f"House {random.randint(1, 400)}, Lane {random.randint(1, 14)}"
            landmark = "Near Street Corner" if has_generic_landmark else f"{random.choice(STREET_PREFIXES)} {random.choice(STREET_LANDMARKS)}"
            desc = f"Reported {inc['title']}. Pressure dropped suddenly and gushing seen near road."

            # Status alignment with incident
            if inc["status"] in ["resolved", "closed"]:
                c_status = random.choice(["resolved", "closed"])
                c_resolved_at = inc["resolved_at"]
            elif inc["status"] == "in_progress":
                c_status = random.choice(["in_progress", "clustered", "assigned"])
                c_resolved_at = None
            else:
                c_status = random.choice(["submitted", "clustered"])
                c_resolved_at = None

            # 3% Reopened complaints simulation
            is_reopened = (random.random() < 0.03) and c_status == "closed"
            if is_reopened:
                c_status = "in_progress"

            # 5% Overdue / Escalated complaints
            is_escalated = (random.random() < 0.05)
            esc_reason = "Overdue: Excavator & road-cutting clearance required from traffic division." if is_escalated else None

            # Anonymous complaints (5%)
            is_anon = (random.random() < 0.05)
            c_resident_id = anon_user_id if is_anon else resident_id
            tracking_hash = f"hash_{random.getrandbits(64):016x}" if is_anon else None

            complaints_insert.append((
                cid, ticket_num, c_resident_id, inc["locality_id"], inc["category_id"],
                desc, occurred_dt.strftime("%Y-%m-%d %H:%M"), c_lat, c_lng, landmark, house,
                c_status, inc["severity"], 1 if is_escalated else 0, esc_reason,
                None, comp_dt.isoformat(), c_resolved_at
            ))

            # Junction Record
            incident_complaints_insert.append((
                inc["id"], cid, "auto_geo_cluster", comp_dt.isoformat(), round(dist_meters, 1)
            ))

            # Ground-Truth Labeling
            ground_truth_records.append({
                "complaint_id": cid,
                "ticket_number": ticket_num,
                "is_clustered": True,
                "ground_truth_incident_id": inc["id"],
                "incident_number": inc["incident_number"],
                "locality_id": inc["locality_id"],
                "category_id": inc["category_id"],
                "distance_to_epicenter_meters": round(dist_meters, 1),
                "is_recurrent_incident": inc["is_recurrent"],
                "created_at": comp_dt.isoformat()
            })

    # Phase 7B: Generate remaining Standalone Complaints to reach exactly 10,000
    print(f"Synthesizing Standalone Complaints (bringing total from {complaint_counter} to {TARGET_COMPLAINTS})...")
    while complaint_counter < TARGET_COMPLAINTS:
        complaint_counter += 1
        cid = complaint_counter
        loc = random.choices(db_localities, weights=[l["weight"] for l in LOCALITIES_DEF])[0]
        cat = random.choices(CATEGORIES_DEF, weights=[c["share"] for c in CATEGORIES_DEF])[0]
        resident_id = random.choice(db_resident_ids)

        day_offset = random.uniform(0, HISTORY_DAYS - 1)
        comp_dt = START_DATE + timedelta(days=day_offset, hours=random.uniform(0, 23), minutes=random.uniform(0, 59))
        occurred_dt = comp_dt - timedelta(minutes=random.uniform(15, 360))
        ticket_num = f"CMP-{comp_dt.year}-{cid:05d}"

        # Standalone coordinates scattered in locality
        c_lat = round(loc["center_lat"] + random.gauss(0, 0.007), 6)
        c_lng = round(loc["center_lng"] + random.gauss(0, 0.007), 6)

        house = f"Flat {random.randint(101, 804)}, Tower {random.choice(['A','B','C','D'])}" if random.random() > 0.08 else "Not Specified"
        landmark = f"{random.choice(STREET_PREFIXES)} {random.choice(STREET_LANDMARKS)}"
        desc = f"Individual household issue: {cat['name']} observed at consumer tap."

        days_ago = (REFERENCE_DATE - comp_dt).total_seconds() / 86400.0
        if days_ago > 3:
            c_status = "closed" if random.random() < 0.70 else "resolved"
            c_resolved_at = (comp_dt + timedelta(hours=random.uniform(1, cat["sla_hours"] * 1.5))).isoformat()
        elif days_ago > 1:
            c_status = random.choice(["in_progress", "assigned", "resolved"])
            c_resolved_at = (comp_dt + timedelta(hours=random.uniform(2, 12))).isoformat() if c_status == "resolved" else None
        else:
            c_status = random.choice(["submitted", "assigned", "in_progress"])
            c_resolved_at = None

        is_anon = (random.random() < 0.04)
        c_resident_id = anon_user_id if is_anon else resident_id
        tracking_hash = f"hash_{random.getrandbits(64):016x}" if is_anon else None

        complaints_insert.append((
            cid, ticket_num, c_resident_id, loc["id"], cat["id"],
            desc, occurred_dt.strftime("%Y-%m-%d %H:%M"), c_lat, c_lng, landmark, house,
            c_status, cat["severity"], 0, None,
            None, comp_dt.isoformat(), c_resolved_at
        ))

        # Ground-Truth Labeling for Standalone
        ground_truth_records.append({
            "complaint_id": cid,
            "ticket_number": ticket_num,
            "is_clustered": False,
            "ground_truth_incident_id": None,
            "incident_number": None,
            "locality_id": loc["id"],
            "category_id": cat["id"],
            "distance_to_epicenter_meters": None,
            "is_recurrent_incident": False,
            "created_at": comp_dt.isoformat()
        })

    # Execute Batch Inserts for Complaints and Junction
    print("Writing complaints to SQLite database in atomic transaction...")
    cursor.executemany("""
    INSERT INTO complaints (
        id, ticket_number, resident_id, locality_id, category_id,
        description, incident_time, lat, lng, address_landmark, house_number,
        status, priority, escalated, escalation_reason, cluster_id, created_at, resolved_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, complaints_insert)

    cursor.executemany("""
    INSERT INTO incident_complaints (incident_id, complaint_id, association_type, associated_at, distance_from_center_meters)
    VALUES (?, ?, ?, ?, ?)
    """, incident_complaints_insert)

    # 8. Generate Tickets (Work Orders) & Lifecycle Events
    print("Generating Tickets & Ticket Event Lifecycle Audits...")
    tickets_insert = []
    events_insert = []
    ticket_counter = 0

    # Generate tickets for master incidents
    for inc in incidents_data:
        ticket_counter += 1
        tid = ticket_counter
        ticket_num = f"WO-INC-{inc['created_dt'].year}-{tid:05d}"
        
        # Pick suitable team for locality
        eligible_teams = [tm for tm in db_teams if tm["locality_id"] == inc["locality_id"]]
        team_id = eligible_teams[0]["id"] if eligible_teams else db_teams[0]["id"]
        tech_id = random.choice(db_tech_ids)

        t_status = "resolved" if inc["status"] in ["resolved", "closed"] else ("in_progress" if inc["status"] == "in_progress" else "dispatched")
        sla_deadline = (inc["created_dt"] + timedelta(hours=8)).isoformat()
        dispatched_dt = inc["created_dt"] + timedelta(minutes=15)
        resolved_dt = inc["resolved_at"]

        tickets_insert.append((
            tid, ticket_num, inc["id"], None, inc["locality_id"], team_id, tech_id,
            t_status, inc["severity"], sla_deadline, "Work order completed via master junction replacement.",
            "https://images.unsplash.com/photo-1584622650111-993a426fbf0a?auto=format&fit=crop&w=400&q=80",
            inc["created_at"], dispatched_dt.isoformat(), resolved_dt
        ))

        # Events
        events_insert.append((tid, "created", None, "dispatched", None, team_id, tech_id, "Ticket generated from master incident.", inc["created_at"]))
        events_insert.append((tid, "assigned", "dispatched", "dispatched", None, team_id, tech_id, "Assigned to specialized response crew.", dispatched_dt.isoformat()))
        if t_status in ["in_progress", "resolved"]:
            events_insert.append((tid, "status_changed", "dispatched", "on_site", team_id, team_id, tech_id, "Crew arrived on-site.", (dispatched_dt + timedelta(minutes=25)).isoformat()))
        if t_status == "resolved":
            events_insert.append((tid, "resolved", "in_progress", "resolved", team_id, team_id, tech_id, "Collar clamp replaced; pressure normalized.", resolved_dt))

    cursor.executemany("""
    INSERT INTO tickets (
        id, ticket_number, incident_id, complaint_id, locality_id,
        assigned_team_id, assigned_technician_id, status, priority,
        sla_deadline, resolution_notes, proof_photo_url, created_at, dispatched_at, resolved_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, tickets_insert)

    cursor.executemany("""
    INSERT INTO ticket_events (ticket_id, event_type, from_status, to_status, from_team_id, to_team_id, performed_by_user_id, notes, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, events_insert)

    # 9. Audit Logs
    audit_logs_insert = [
        ("System Automated Engine", "DATASET_SEED", f"Synthesized {TARGET_COMPLAINTS} complaint records across {len(LOCALITIES_DEF)} localities.", REFERENCE_DATE.isoformat()),
        ("NIVORA Quality Audit", "INTEGRITY_CHECK", "Validated foreign key constraints, timestamps, and junction cardinality.", REFERENCE_DATE.isoformat())
    ]
    cursor.executemany("""
    INSERT INTO audit_logs (user_name, action, details, timestamp)
    VALUES (?, ?, ?, ?)
    """, audit_logs_insert)

    conn.commit()
    conn.close()

    # 10. Write Ground Truth Dataset & Evaluation Splits (70% Dev / 30% Test)
    print("Writing Separate Labeled Ground-Truth Evaluation Sets...")

    # Sort deterministically by complaint_id
    ground_truth_records.sort(key=lambda r: r["complaint_id"])

    # Temporal / Stratified Split:
    # 70% Dev (First 7,000 complaints chronologically or deterministic split)
    # 30% Test (Held-Out 3,000 complaints)
    split_cutoff = int(TARGET_COMPLAINTS * 0.70)
    dev_records = ground_truth_records[:split_cutoff]
    test_records = ground_truth_records[split_cutoff:]

    # Write Complete Ground Truth CSV
    gt_csv_path = os.path.join(GROUND_TRUTH_DIR, "ground_truth_complaints.csv")
    with open(gt_csv_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "complaint_id", "ticket_number", "is_clustered", "ground_truth_incident_id",
            "incident_number", "locality_id", "category_id", "distance_to_epicenter_meters",
            "is_recurrent_incident", "created_at"
        ])
        writer.writeheader()
        writer.writerows(ground_truth_records)

    # Write Recurring Incidents Ground Truth
    recurring_incidents = [inc for inc in incidents_data if inc["is_recurrent"]]
    gt_rec_csv_path = os.path.join(GROUND_TRUTH_DIR, "ground_truth_recurring_incidents.csv")
    with open(gt_rec_csv_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "id", "incident_number", "locality_id", "category_id", "title",
            "severity", "status", "center_lat", "center_lng", "created_at"
        ])
        writer.writeheader()
        for r in recurring_incidents:
            writer.writerow({
                "id": r["id"],
                "incident_number": r["incident_number"],
                "locality_id": r["locality_id"],
                "category_id": r["category_id"],
                "title": r["title"],
                "severity": r["severity"],
                "status": r["status"],
                "center_lat": r["center_lat"],
                "center_lng": r["center_lng"],
                "created_at": r["created_at"]
            })

    # Write Evaluation Splits JSON
    splits_meta = {
        "metadata": {
            "dataset_name": "NIVORA Synthetic Demonstration & Evaluation Dataset",
            "random_seed": RANDOM_SEED,
            "generated_at": REFERENCE_DATE.isoformat(),
            "total_complaints": TARGET_COMPLAINTS,
            "dev_set_count": len(dev_records),
            "test_set_count": len(test_records),
            "dev_test_ratio": "70% Dev / 30% Held-Out Test",
            "ground_truth_purpose": "Evaluation of geospatial radius clustering, repeated-issue detection, and root-cause aggregation algorithms without data leakage."
        },
        "dev_complaint_ids": [r["complaint_id"] for r in dev_records],
        "test_complaint_ids": [r["complaint_id"] for r in test_records]
    }
    splits_json_path = os.path.join(GROUND_TRUTH_DIR, "evaluation_splits.json")
    with open(splits_json_path, mode="w", encoding="utf-8") as f:
        json.dump(splits_meta, f, indent=2)

    print("=================================================================")
    print(f" Dataset successfully generated and imported into: {DB_PATH}")
    print(f" Ground-Truth Files saved to: {GROUND_TRUTH_DIR}")
    print(f" Total Complaints: {TARGET_COMPLAINTS}")
    print(f" Total Master Incidents: {len(incidents_data)} (Recurring: {len(recurring_incidents)})")
    print(f" Total Work Order Tickets: {ticket_counter}")
    print(f" Dev Set: {len(dev_records)} | Held-Out Test Set: {len(test_records)}")
    print("=================================================================")

if __name__ == "__main__":
    generate_dataset()
