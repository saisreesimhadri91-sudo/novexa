"""
NIVORA WATER MANAGEMENT SYSTEM — PHASE 5 INTEGRATION TEST SUITE
Comprehensive verification of Frontend-to-Backend integration and end-to-end user journeys:
1. Citizen complaint registration with GPS coordinates & landmark validation.
2. Separation of observed incident time vs database creation timestamp.
3. Proximity cluster query & 1-tap neighborhood cluster join.
4. Central Operations dispatch & technician work-order assignment (syncing tickets & ticket_events).
5. Field Service Team status progression: Arrived on-site -> Complete with photo proof.
6. Citizen resolution confirmation with 5-star rating & feedback persistence.
7. Supervisor priority overrides on master incidents with mandatory justification.
8. Incident merging into master infrastructure failures & incident splitting / decoupling.
9. Locality health analytics across all 15 wards & executive performance KPIs.
10. Streaming operational CSV export with RFC 4180 headers.
11. Role-based privacy preservation and PII masking.
"""

import unittest
import json
import sqlite3
import os
import sys
import threading
import http.client
from http.server import HTTPServer

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT_DIR)

from server import NivoraAPIHandler
import backend.database as db_module

TEST_PORT = 8016


class TestPhase5Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", TEST_PORT), NivoraAPIHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _api_get(self, path):
        conn = http.client.HTTPConnection("127.0.0.1", TEST_PORT, timeout=10)
        conn.request("GET", path)
        res = conn.getresponse()
        data = res.read()
        conn.close()
        return res.status, res.getheaders(), data

    def _api_post(self, path, payload):
        conn = http.client.HTTPConnection("127.0.0.1", TEST_PORT, timeout=10)
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        conn.request("POST", path, body=body, headers=headers)
        res = conn.getresponse()
        data = res.read()
        conn.close()
        return res.status, res.getheaders(), data

    # -------------------------------------------------------------
    # User Journey 1: Citizen Complaint Registration
    # -------------------------------------------------------------
    def test_01_citizen_complaint_registration_e2e(self):
        payload = {
            "resident_id": 1,
            "locality_id": 1,
            "category_id": 1,  # Pipe Leak
            "incident_time": "2026-10-24 18:30",
            "lat": 28.6291,
            "lng": 77.2093,
            "address_landmark": "Opposite Gate 3, High-Pressure Substation",
            "house_number": "Apartment 402",
            "description": "Continuous leak noticed at junction valve.",
            "priority": "high"
        }
        status, headers, body = self._api_post("/api/complaints", payload)
        self.assertEqual(status, 200, f"Expected HTTP 200, got {status}: {body.decode()}")
        res_json = json.loads(body.decode())
        self.assertTrue(res_json["success"])
        ticket_num = res_json["ticket_number"]
        complaint_id = res_json["complaint_id"]
        self.assertTrue(ticket_num.startswith("TKT-2026-"))

        # Verify DB persistence directly in nivora.db
        conn = db_module.get_connection()
        c = conn.cursor()
        c.execute("SELECT ticket_number, resident_id, incident_time, address_landmark, house_number, status, priority, created_at FROM complaints WHERE id = ?", (complaint_id,))
        row = c.fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row["ticket_number"], ticket_num)
        self.assertEqual(row["incident_time"], "2026-10-24 18:30")
        self.assertEqual(row["address_landmark"], "Opposite Gate 3, High-Pressure Substation")
        self.assertEqual(row["house_number"], "Apartment 402")
        self.assertIn(row["status"], ["submitted", "clustered"])
        self.assertNotEqual(row["created_at"], row["incident_time"], "Occurrence time must be preserved separately from created_at")
        print(f"PASS: Journey 1 — Citizen registered complaint {ticket_num} (ID: {complaint_id}) with distinct timestamps.")

    # -------------------------------------------------------------
    # User Journey 2: 1-Tap Neighborhood Cluster Confirmation
    # -------------------------------------------------------------
    def test_02_quick_link_cluster_e2e(self):
        # First query active clusters
        status, _, body = self._api_get("/api/clusters")
        self.assertEqual(status, 200)
        clusters = json.loads(body.decode())["clusters"]
        self.assertGreater(len(clusters), 0, "At least 1 active cluster must exist")
        target_cluster = clusters[0]
        initial_count = target_cluster["complaint_count"]

        # Resident performs 1-tap join
        payload = {
            "cluster_id": target_cluster["id"],
            "resident_id": 2,
            "address_landmark": "Sector 4 Main Corridor Gate 2",
            "house_number": "Flat 305",
            "incident_time": "2026-10-24 19:15",
            "lat": target_cluster["center_lat"],
            "lng": target_cluster["center_lng"]
        }
        status, _, body = self._api_post("/api/complaints/quick-link", payload)
        self.assertEqual(status, 200)
        data = json.loads(body.decode())
        self.assertTrue(data["success"])
        self.assertEqual(data["new_count"], initial_count + 1)
        self.assertEqual(data["cluster_code"], target_cluster["cluster_code"])
        print(f"PASS: Journey 2 — 1-Tap confirmed to cluster {target_cluster['cluster_code']} (Count incremented: {initial_count} -> {data['new_count']}).")

    # -------------------------------------------------------------
    # User Journey 3: Dispatch & Technician Work-Order Sync
    # -------------------------------------------------------------
    def test_03_dispatch_and_work_order_sync_e2e(self):
        # Create a fresh complaint to dispatch
        payload = {
            "resident_id": 3,
            "locality_id": 2,
            "category_id": 2,  # Contamination
            "incident_time": "2026-10-24 19:30",
            "lat": 28.6145,
            "lng": 77.1985,
            "address_landmark": "Near Community Center Water Tank",
            "house_number": "House 12",
            "description": "Murky water observed after supply opened.",
            "priority": "critical"
        }
        _, _, body = self._api_post("/api/complaints", payload)
        complaint_id = json.loads(body.decode())["complaint_id"]

        # Admin assigns Technician ID 6
        assign_payload = {
            "complaint_id": complaint_id,
            "technician_id": 6
        }
        status, _, body = self._api_post("/api/assignments/assign", assign_payload)
        self.assertEqual(status, 200)
        data = json.loads(body.decode())
        self.assertTrue(data["success"])

        # Check DB synchronization across service_assignments, complaints, tickets, ticket_events
        conn = db_module.get_connection()
        c = conn.cursor()
        c.execute("SELECT status FROM complaints WHERE id = ?", (complaint_id,))
        self.assertEqual(c.fetchone()["status"], "assigned")

        c.execute("SELECT status, technician_id FROM service_assignments WHERE complaint_id = ?", (complaint_id,))
        sa_row = c.fetchone()
        self.assertIsNotNone(sa_row)
        self.assertEqual(sa_row["status"], "dispatched")
        self.assertEqual(sa_row["technician_id"], 6)

        c.execute("SELECT id, status, assigned_technician_id FROM tickets WHERE complaint_id = ?", (complaint_id,))
        tk_row = c.fetchone()
        self.assertIsNotNone(tk_row, "A synchronized tickets record must be present")
        self.assertEqual(tk_row["status"], "dispatched")
        self.assertEqual(tk_row["assigned_technician_id"], 6)

        c.execute("SELECT event_type, to_status FROM ticket_events WHERE ticket_id = ?", (tk_row["id"],))
        te_row = c.fetchone()
        self.assertIsNotNone(te_row, "A ticket event audit entry must be logged")
        self.assertEqual(te_row["to_status"], "dispatched")
        conn.close()

        print(f"PASS: Journey 3 — Assigned crew synced across complaints, service_assignments, tickets, and ticket_events.")

    # -------------------------------------------------------------
    # User Journey 4: Field Technician Arrived On-Site -> Proof Resolution
    # -------------------------------------------------------------
    def test_04_technician_status_progression_e2e(self):
        # Query assigned work orders for Technician 6
        status, _, body = self._api_get("/api/complaints?role=technician&user_id=6")
        self.assertEqual(status, 200)
        jobs = json.loads(body.decode())["complaints"]
        self.assertGreater(len(jobs), 0)
        target_job = jobs[0]
        complaint_id = target_job["id"]

        # Step 4a: Mark Arrived On-Site
        status, _, body = self._api_post("/api/assignments/update-status", {
            "complaint_id": complaint_id,
            "technician_id": 6,
            "status": "on_site",
            "notes": "Arrived at location. Began ultrasonic pipe inspection."
        })
        self.assertEqual(status, 200)

        conn = db_module.get_connection()
        c = conn.cursor()
        c.execute("SELECT status FROM complaints WHERE id = ?", (complaint_id,))
        self.assertEqual(c.fetchone()["status"], "in_progress")
        conn.close()

        # Step 4b: Complete Job with Proof Photo URL
        status, _, body = self._api_post("/api/assignments/update-status", {
            "complaint_id": complaint_id,
            "technician_id": 6,
            "status": "completed",
            "notes": "Replaced fractured collar and flushed supply line. Water clear, 3.2 bar pressure confirmed.",
            "proof_photo_url": "https://images.unsplash.com/photo-1584622650111-993a426fbf0a"
        })
        self.assertEqual(status, 200)

        conn = db_module.get_connection()
        c = conn.cursor()
        c.execute("SELECT status, resolved_at FROM complaints WHERE id = ?", (complaint_id,))
        comp_row = c.fetchone()
        self.assertEqual(comp_row["status"], "resolved")
        self.assertIsNotNone(comp_row["resolved_at"])

        c.execute("SELECT status, proof_photo_url, completed_at FROM service_assignments WHERE complaint_id = ?", (complaint_id,))
        sa_row = c.fetchone()
        self.assertEqual(sa_row["status"], "completed")
        self.assertIn("unsplash", sa_row["proof_photo_url"])
        self.assertIsNotNone(sa_row["completed_at"])
        conn.close()

        print(f"PASS: Journey 4 — Technician on-site update & photo-proof resolution successfully persisted.")

    # -------------------------------------------------------------
    # User Journey 5: Citizen Confirms Resolution & 5-Star Feedback
    # -------------------------------------------------------------
    def test_05_citizen_resolution_confirmation_e2e(self):
        # Query resolved complaints
        conn = db_module.get_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM complaints WHERE status = 'resolved' LIMIT 1")
        row = c.fetchone()
        conn.close()
        self.assertIsNotNone(row)
        complaint_id = row["id"]

        # Citizen submits confirmation rating
        status, _, body = self._api_post("/api/complaints/confirm-resolution", {
            "complaint_id": complaint_id,
            "rating": 5,
            "comment": "Water pressure restored immediately. Excellent service!"
        })
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body.decode())["success"])

        # Check DB status is closed and feedback saved
        conn = db_module.get_connection()
        c = conn.cursor()
        c.execute("SELECT status FROM complaints WHERE id = ?", (complaint_id,))
        self.assertEqual(c.fetchone()["status"], "closed")

        c.execute("SELECT rating, comment FROM feedback WHERE complaint_id = ?", (complaint_id,))
        fb_row = c.fetchone()
        self.assertIsNotNone(fb_row)
        self.assertEqual(fb_row["rating"], 5)
        self.assertIn("restored", fb_row["comment"])
        conn.close()

        print(f"PASS: Journey 5 — Citizen confirmed resolution and recorded 5-star rating.")

    # -------------------------------------------------------------
    # User Journey 6: Supervisor Priority Override & Escalation
    # -------------------------------------------------------------
    def test_06_supervisor_priority_override_e2e(self):
        # Find active incident
        conn = db_module.get_connection()
        c = conn.cursor()
        c.execute("SELECT id, incident_number FROM incidents LIMIT 1")
        inc_row = c.fetchone()
        conn.close()
        self.assertIsNotNone(inc_row)
        incident_id = inc_row["id"]

        # Override severity to critical
        status, _, body = self._api_post("/api/incidents/override-priority", {
            "incident_id": incident_id,
            "new_priority": "critical",
            "justification": "Main line burst causing water outage to hospital feeder line.",
            "supervisor_name": "Ward Supervisor Singh"
        })
        self.assertEqual(status, 200)
        data = json.loads(body.decode())
        self.assertTrue(data["success"])
        self.assertEqual(data["new_priority"], "critical")

        # Verify DB update in incidents and audit_logs
        conn = db_module.get_connection()
        c = conn.cursor()
        c.execute("SELECT severity FROM incidents WHERE id = ?", (incident_id,))
        self.assertEqual(c.fetchone()["severity"], "critical")

        c.execute("SELECT details FROM audit_logs WHERE action = 'PRIORITY_OVERRIDE' ORDER BY id DESC LIMIT 1")
        audit_row = c.fetchone()
        self.assertIsNotNone(audit_row)
        self.assertIn("hospital feeder line", audit_row["details"])
        conn.close()

        print(f"PASS: Journey 6 — Supervisor priority override applied and verified in audit log.")

    # -------------------------------------------------------------
    # User Journey 7: Incident Merging & Splitting
    # -------------------------------------------------------------
    def test_07_incident_merge_and_split_e2e(self):
        conn = db_module.get_connection()
        c = conn.cursor()
        c.execute("SELECT id, incident_number FROM incidents LIMIT 1")
        inc = c.fetchone()
        c.execute("SELECT id FROM complaints WHERE status = 'submitted' LIMIT 1")
        comp = c.fetchone()
        conn.close()

        # Step 7a: Merge complaint into incident
        status, _, body = self._api_post("/api/incidents/merge", {
            "master_incident_id": inc["id"],
            "complaint_ids": [comp["id"]],
            "reason": "Direct hydraulic link to trunk line pipe leak."
        })
        self.assertEqual(status, 200)
        data = json.loads(body.decode())
        self.assertTrue(data["success"])
        self.assertEqual(data["merged_complaints_count"], 1)

        # Step 7b: Decouple / Split complaint from incident
        status, _, body = self._api_post("/api/incidents/split", {
            "incident_id": inc["id"],
            "complaint_id": comp["id"],
            "reason": "Determined to be internal building plumbing issue."
        })
        self.assertEqual(status, 200)
        data = json.loads(body.decode())
        self.assertTrue(data["success"])

        # Check DB junction link is deleted
        conn = db_module.get_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM incident_complaints WHERE incident_id = ? AND complaint_id = ?", (inc["id"], comp["id"]))
        self.assertIsNone(c.fetchone())
        conn.close()

        print(f"PASS: Journey 7 — Admin merge and split verified with junction cardinality preservation.")

    # -------------------------------------------------------------
    # User Journey 8: Locality Health Analytics & Performance KPIs
    # -------------------------------------------------------------
    def test_08_locality_health_and_performance_e2e(self):
        status, _, body = self._api_get("/api/analytics/locality")
        self.assertEqual(status, 200)
        data = json.loads(body.decode())
        localities = data["localities"]
        self.assertEqual(len(localities), 15, "All 15 wards must have computed health scores")
        for loc in localities:
            self.assertIn("health_score", loc)
            self.assertGreaterEqual(loc["health_score"], 0)
            self.assertLessEqual(loc["health_score"], 100)
            self.assertIn("pipeline_grid", loc)

        status, _, body = self._api_get("/api/analytics/performance")
        self.assertEqual(status, 200)
        perf = json.loads(body.decode())["performance"]
        self.assertIn("sla_compliance_rate", perf)
        self.assertIn("mean_time_to_resolve_hours", perf)
        self.assertGreaterEqual(perf["sla_compliance_rate"], 90.0)
        self.assertEqual(len(perf["category_distribution"]), 5)
        print(f"PASS: Journey 8 — Locality health scores & SLA compliance metrics verified.")

    # -------------------------------------------------------------
    # User Journey 9: Operational CSV Streaming Export
    # -------------------------------------------------------------
    def test_09_operational_csv_stream_export_e2e(self):
        status, headers, body = self._api_get("/api/reports/export/csv")
        self.assertEqual(status, 200)
        h_dict = dict(headers)
        self.assertIn("text/csv", h_dict.get("Content-Type", ""))
        self.assertIn("attachment; filename=nivora_export_", h_dict.get("Content-Disposition", ""))

        csv_text = body.decode("utf-8")
        lines = csv_text.strip().split("\n")
        self.assertGreaterEqual(len(lines), 500, "Export should stream operational complaints records")
        header_row = lines[0]
        self.assertIn("Ticket Number", header_row)
        self.assertIn("Locality", header_row)
        self.assertIn("Observed Time", header_row)
        print(f"PASS: Journey 9 — Operational CSV streamed ({len(lines)} rows, RFC 4180 format).")

    # -------------------------------------------------------------
    # User Journey 10: Role-Based PII Privacy Preservation
    # -------------------------------------------------------------
    def test_10_role_based_pii_privacy_e2e(self):
        # Technician view must mask telephone
        status, _, body = self._api_get("/api/complaints?role=technician&user_id=6")
        self.assertEqual(status, 200)
        tech_complaints = json.loads(body.decode())["complaints"]
        for c in tech_complaints[:10]:
            phone = c.get("resident_phone")
            if phone and phone != "[Protected]":
                self.assertIn("****", phone, f"Technician view must mask citizen phone: {phone}")

        # Resident view preserves full phone for their own record
        status, _, body = self._api_get("/api/complaints?role=resident&user_id=1")
        self.assertEqual(status, 200)
        resident_complaints = json.loads(body.decode())["complaints"]
        for c in resident_complaints:
            phone = c.get("resident_phone")
            if phone:
                self.assertNotIn("****", phone, "Resident must see their own unmasked phone")

        print(f"PASS: Journey 10 — Role-based PII privacy and masking verified across roles.")


if __name__ == "__main__":
    unittest.main()
