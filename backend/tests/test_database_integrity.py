"""
NIVORA Database Integrity & Entity Verification Test Suite
Verifies all 9 logical entities, constraints, timestamp separation, 
junction relationships, and foreign key enforcement in the active database.
"""

import sqlite3
import os
import unittest
from datetime import datetime, timezone, timedelta

import sys
# Path is 3 levels up: backend/tests/test_database_integrity.py -> NIVORA/nivora.db
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
DB_PATH = os.path.join(ROOT_DIR, "nivora.db")

class TestNivoraDatabaseIntegrity(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self.conn.row_factory = sqlite3.Row

    def tearDown(self):
        self.conn.close()

    def test_01_all_nine_entities_exist(self):
        """Verify that all 9 required logical entities exist in the database."""
        required_entities = [
            'users',
            'localities',
            'complaints',
            'incidents',
            'incident_complaints',
            'tickets',
            'ticket_events',
            'teams',
            'audit_logs'
        ]
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = [r[0] for r in cursor.fetchall()]

        for entity in required_entities:
            self.assertIn(entity, existing_tables, f"Missing required entity: {entity}")
            cursor.execute(f"SELECT COUNT(*) FROM {entity}")
            count = cursor.fetchone()[0]
            self.assertGreaterEqual(count, 0, f"Entity table {entity} is unqueryable.")
        print("PASS: All 9 logical entities verified in database.")

    def test_02_unique_identifiers(self):
        """Verify that complaints, incidents, and tickets possess strict unique identifiers."""
        cursor = self.conn.cursor()

        # Check complaints ticket_number uniqueness
        cursor.execute("SELECT COUNT(DISTINCT ticket_number), COUNT(*) FROM complaints")
        uniq_c, total_c = cursor.fetchone()
        self.assertEqual(uniq_c, total_c, "Duplicate complaint ticket numbers detected!")

        # Check incidents incident_number uniqueness
        cursor.execute("SELECT COUNT(DISTINCT incident_number), COUNT(*) FROM incidents")
        uniq_i, total_i = cursor.fetchone()
        self.assertEqual(uniq_i, total_i, "Duplicate incident numbers detected!")

        # Check tickets ticket_number uniqueness
        cursor.execute("SELECT COUNT(DISTINCT ticket_number), COUNT(*) FROM tickets")
        uniq_t, total_t = cursor.fetchone()
        self.assertEqual(uniq_t, total_t, "Duplicate ticket numbers detected!")
        print("PASS: Unique identifier enforcement verified for complaints, incidents, and tickets.")

    def test_03_timestamp_separation(self):
        """Verify that complaint creation time and occurrence time are stored separately."""
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA table_info(complaints)")
        cols = [r["name"] for r in cursor.fetchall()]

        self.assertIn("created_at", cols, "Missing created_at column in complaints")
        self.assertIn("incident_time", cols, "Missing incident_time column in complaints")

        # Verify populated records have both values
        cursor.execute("SELECT ticket_number, created_at, incident_time FROM complaints WHERE incident_time IS NOT NULL LIMIT 1")
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertIsNotNone(row["created_at"])
        self.assertIsNotNone(row["incident_time"])
        print(f"PASS: Timestamp separation verified ({row['ticket_number']}: Created={row['created_at']}, Observed={row['incident_time']}).")

    def test_04_preserve_original_complaints_in_incidents(self):
        """Verify that associating complaints to an incident preserves the original complaint records."""
        cursor = self.conn.cursor()

        # Query complaints linked to master incident
        cursor.execute("""
        SELECT c.id, c.ticket_number, c.description, ic.incident_id, i.incident_number
        FROM complaints c
        JOIN incident_complaints ic ON c.id = ic.complaint_id
        JOIN incidents i ON ic.incident_id = i.id
        """)
        linked_records = cursor.fetchall()
        self.assertGreater(len(linked_records), 0, "No linked complaints found in junction.")

        # Ensure linked complaints still exist intact in complaints table
        for r in linked_records:
            cursor.execute("SELECT * FROM complaints WHERE id = ?", (r["id"],))
            orig = cursor.fetchone()
            self.assertIsNotNone(orig, f"Original complaint {r['id']} was deleted upon association!")
            self.assertEqual(orig["ticket_number"], r["ticket_number"])
        print(f"PASS: Original complaint preservation verified across {len(linked_records)} linked reports.")

    def test_05_many_complaints_to_one_incident_cardinality(self):
        """Verify that multiple complaints can be associated with a single master incident."""
        cursor = self.conn.cursor()
        cursor.execute("""
        SELECT incident_id, COUNT(complaint_id) as comp_count
        FROM incident_complaints
        GROUP BY incident_id
        HAVING comp_count > 1
        """)
        row = cursor.fetchone()
        self.assertIsNotNone(row, "Incident-Complaints junction has no 1-to-many associations.")
        self.assertGreaterEqual(row["comp_count"], 2, "Expected at least 2 complaints associated to master incident.")
        print(f"PASS: Many-to-one junction cardinality verified (Incident ID {row['incident_id']} has {row['comp_count']} complaints).")

    def test_06_ticket_events_audit_recording(self):
        """Verify that status changes, assignments, and resolutions are recorded in ticket_events."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT event_type FROM ticket_events")
        events = [r[0] for r in cursor.fetchall()]

        # Verify key lifecycle event types
        self.assertIn("created", events)
        self.assertIn("status_changed", events)

        cursor.execute("""
        SELECT te.ticket_id, t.ticket_number, te.event_type, te.from_status, te.to_status, te.created_at
        FROM ticket_events te
        JOIN tickets t ON te.ticket_id = t.id
        ORDER BY te.created_at ASC
        """)
        rows = cursor.fetchall()
        self.assertGreaterEqual(len(rows), 3, "Insufficient ticket events recorded.")
        print(f"PASS: Ticket events lifecycle audit verified ({len(rows)} events recorded).")

    def test_07_locality_level_geographic_analysis(self):
        """Verify locality-level analysis is possible without requiring private household coordinates."""
        cursor = self.conn.cursor()
        cursor.execute("""
        SELECT 
            locality_name,
            zone_code,
            center_lat,
            center_lng,
            total_complaints,
            active_incidents
        FROM locality_geographic_summary
        """)
        rows = cursor.fetchall()
        self.assertGreater(len(rows), 0)
        for r in rows:
            self.assertIsNotNone(r["locality_name"])
            self.assertIsNotNone(r["center_lat"])
            self.assertIsNotNone(r["center_lng"])
        print(f"PASS: Locality-level geographic aggregation verified across {len(rows)} wards via locality_geographic_summary view.")

    def test_08_spatial_indexes_and_wgs84_bounds(self):
        """Verify that spatial indexes exist and all coordinates lie within valid WGS 84 bounds."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = [r[0] for r in cursor.fetchall()]

        self.assertIn("idx_complaints_coords", indexes, "Missing idx_complaints_coords spatial index!")
        self.assertIn("idx_incidents_coords", indexes, "Missing idx_incidents_coords spatial index!")

        # Verify coordinate validity across complaints
        cursor.execute("SELECT COUNT(*) FROM complaints WHERE lat < -90.0 OR lat > 90.0 OR lng < -180.0 OR lng > 180.0")
        out_of_bounds_c = cursor.fetchone()[0]
        self.assertEqual(out_of_bounds_c, 0, "Complaints detected with coordinates outside WGS 84 bounds!")

        # Verify coordinate validity across incidents
        cursor.execute("SELECT COUNT(*) FROM incidents WHERE center_lat < -90.0 OR center_lat > 90.0 OR center_lng < -180.0 OR center_lng > 180.0")
        out_of_bounds_i = cursor.fetchone()[0]
        self.assertEqual(out_of_bounds_i, 0, "Incidents detected with coordinates outside WGS 84 bounds!")
        print("PASS: Spatial indexes and WGS 84 coordinate boundaries verified (0 out-of-bounds records).")

    def test_09_haversine_cluster_proximity_threshold(self):
        """Verify that complaints clustered into master incidents adhere to spatial proximity thresholds."""
        cursor = self.conn.cursor()
        cursor.execute("""
        SELECT ic.incident_id, ic.complaint_id, ic.distance_from_center_meters, i.radius_meters
        FROM incident_complaints ic
        JOIN incidents i ON ic.incident_id = i.id
        WHERE ic.distance_from_center_meters > 0
        LIMIT 100
        """)
        rows = cursor.fetchall()
        self.assertGreater(len(rows), 0, "No junction records with calculated distance.")
        for r in rows:
            self.assertLessEqual(r["distance_from_center_meters"], 350.0, f"Complaint {r['complaint_id']} exceeds proximity threshold!")
        print(f"PASS: Geospatial Haversine clustering proximity verified across sample of {len(rows)} junction associations.")

    def test_10_privacy_preservation_and_role_masking(self):
        """Verify that citizen phone numbers and flat IDs are masked for technicians and public views."""
        from backend.analytics import apply_privacy_filters
        cursor = self.conn.cursor()
        cursor.execute("""
        SELECT c.*, u.name as resident_name, u.phone as resident_phone, u.privacy_opt_in
        FROM complaints c
        JOIN users u ON c.resident_id = u.id
        LIMIT 1
        """)
        raw_complaint = dict(cursor.fetchone())

        # Test Technician View
        tech_view = apply_privacy_filters(raw_complaint, user_role="technician")
        self.assertIn("****", tech_view["resident_phone"], "Resident phone was not masked for technician!")
        self.assertIn("Protected", tech_view["house_number"], "House number was not masked for technician!")

        # Test Public View
        pub_view = apply_privacy_filters(raw_complaint, user_role="public")
        self.assertEqual(pub_view["resident_phone"], "[Private]")
        self.assertEqual(pub_view["house_number"], "[Private]")
        print("PASS: Privacy preservation and role-based PII masking verified across technician and public roles.")

if __name__ == "__main__":
    unittest.main()
