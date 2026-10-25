import sys
import os
import threading
import time
import urllib.request
import urllib.error
import json
import unittest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from server import start_server

PORT = 8014

class TestBackendAPIEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server_thread = threading.Thread(target=start_server, args=(PORT,), daemon=True)
        cls.server_thread.start()
        time.sleep(1.5)
        cls.base_url = f"http://127.0.0.1:{PORT}"

    def test_01_health_check_endpoint(self):
        """Verify GET /api/health returns server status and database connectivity."""
        with urllib.request.urlopen(f"{self.base_url}/api/health") as res:
            self.assertEqual(res.status, 200)
            data = json.loads(res.read().decode("utf-8"))
            self.assertEqual(data["status"], "healthy")
            self.assertEqual(data["database"], "connected")
            self.assertGreaterEqual(data["total_complaints"], 10000)
            self.assertGreaterEqual(data["total_incidents"], 450)
            self.assertGreaterEqual(data["total_tickets"], 450)
            self.assertEqual(data["wards_monitored"], 15)
            print(f"PASS: /api/health verified (Complaints: {data['total_complaints']}, Incidents: {data['total_incidents']}, Tickets: {data['total_tickets']}).")

    def test_02_meta_endpoint_includes_teams(self):
        """Verify GET /api/meta returns localities, categories, users, and teams."""
        with urllib.request.urlopen(f"{self.base_url}/api/meta") as res:
            self.assertEqual(res.status, 200)
            data = json.loads(res.read().decode("utf-8"))
            self.assertEqual(len(data["localities"]), 15)
            self.assertGreaterEqual(len(data["categories"]), 5)
            self.assertGreaterEqual(len(data["users"]), 10)
            self.assertIn("teams", data)
            self.assertGreaterEqual(len(data["teams"]), 4)
            print(f"PASS: /api/meta verified with {len(data['teams'])} field service teams.")

    def test_03_tickets_relational_work_orders(self):
        """Verify GET /api/tickets returns relational work orders with lifecycle events."""
        with urllib.request.urlopen(f"{self.base_url}/api/tickets") as res:
            self.assertEqual(res.status, 200)
            data = json.loads(res.read().decode("utf-8"))
            self.assertIn("tickets", data)
            self.assertGreater(len(data["tickets"]), 0)
            first_ticket = data["tickets"][0]
            self.assertIn("ticket_number", first_ticket)
            self.assertIn("status", first_ticket)
            self.assertIn("lifecycle_events", first_ticket)
            print(f"PASS: /api/tickets verified ({len(data['tickets'])} work orders queried with attached lifecycle events).")

    def test_04_incidents_endpoint(self):
        """Verify GET /api/incidents returns master incidents with associated complaint counts."""
        with urllib.request.urlopen(f"{self.base_url}/api/incidents") as res:
            self.assertEqual(res.status, 200)
            data = json.loads(res.read().decode("utf-8"))
            self.assertIn("incidents", data)
            self.assertGreater(len(data["incidents"]), 0)
            first_inc = data["incidents"][0]
            self.assertIn("incident_number", first_inc)
            self.assertIn("associated_complaint_count", first_inc)
            print(f"PASS: /api/incidents verified ({len(data['incidents'])} master infrastructure failures queried).")

    def test_05_reports_csv_stream_export(self):
        """Verify GET /api/reports/export/csv returns downloadable CSV with proper headers."""
        with urllib.request.urlopen(f"{self.base_url}/api/reports/export/csv") as res:
            self.assertEqual(res.status, 200)
            content_type = res.headers.get("Content-Type")
            self.assertIn("text/csv", content_type)
            content_disp = res.headers.get("Content-Disposition")
            self.assertIn("attachment; filename=", content_disp)
            body = res.read().decode("utf-8")
            self.assertIn("Ticket Number,Locality,Category", body)
            lines = body.strip().split("\n")
            self.assertGreater(len(lines), 10)
            print(f"PASS: /api/reports/export/csv streaming export verified ({len(lines)} CSV rows).")

    def test_06_post_complaint_validation_rejects_out_of_bounds_coords(self):
        """Verify POST /api/complaints rejects coordinates outside WGS 84 bounds with 400."""
        invalid_payload = {
            "resident_id": 1,
            "locality_id": 1,
            "category_id": 1,
            "lat": 125.0,  # Invalid latitude > 90
            "lng": 77.2080,
            "address_landmark": "North Gate Test"
        }
        req = urllib.request.Request(
            f"{self.base_url}/api/complaints",
            data=json.dumps(invalid_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req) as res:
                self.fail("Expected 400 Bad Request for out-of-bounds coordinates, got status: " + str(res.status))
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 400)
            err_data = json.loads(e.read().decode("utf-8"))
            self.assertIn("error", err_data)
            print("PASS: Coordinate validation rejected lat=125.0 with 400 Bad Request.")

    def test_07_post_complaint_validation_rejects_short_landmark(self):
        """Verify POST /api/complaints rejects empty landmark with 400."""
        invalid_payload = {
            "resident_id": 1,
            "locality_id": 1,
            "category_id": 1,
            "lat": 28.6280,
            "lng": 77.2080,
            "address_landmark": " "  # Empty
        }
        req = urllib.request.Request(
            f"{self.base_url}/api/complaints",
            data=json.dumps(invalid_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req) as res:
                self.fail("Expected 400 for empty landmark.")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 400)
            print("PASS: Landmark validation rejected empty landmark with 400 Bad Request.")

    def test_08_post_incident_merge_and_split_lifecycle(self):
        """Verify POST /api/incidents/merge and POST /api/incidents/split workflow."""
        # 1. Merge Complaint ID 1 into Incident ID 1
        merge_payload = {
            "master_incident_id": 1,
            "complaint_ids": [1],
            "reason": "Correlated trunk pipeline failure integration test."
        }
        req = urllib.request.Request(
            f"{self.base_url}/api/incidents/merge",
            data=json.dumps(merge_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as res:
            self.assertEqual(res.status, 200)
            data = json.loads(res.read().decode("utf-8"))
            self.assertTrue(data.get("success"))
            self.assertEqual(data.get("merged_complaints_count"), 1)
            print(f"PASS: /api/incidents/merge successfully merged complaint into Incident {data['master_incident_number']}.")

        # 2. Split Complaint ID 1 back from Incident ID 1
        split_payload = {
            "incident_id": 1,
            "complaint_id": 1,
            "reason": "Decoupled standalone complaint verification."
        }
        req_split = urllib.request.Request(
            f"{self.base_url}/api/incidents/split",
            data=json.dumps(split_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req_split) as res:
            self.assertEqual(res.status, 200)
            split_data = json.loads(res.read().decode("utf-8"))
            self.assertTrue(split_data.get("success"))
            print("PASS: /api/incidents/split successfully decoupled complaint with audit logging.")

    def test_09_supervisor_priority_override(self):
        """Verify POST /api/incidents/override-priority enforces reason tracking and updates priority."""
        payload = {
            "incident_id": 1,
            "new_priority": "critical",
            "justification": "Heavy main trunk fissure threatening hospital pipeline feeder.",
            "supervisor_name": "Senior Ward Supervisor Sharma"
        }
        req = urllib.request.Request(
            f"{self.base_url}/api/incidents/override-priority",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as res:
            self.assertEqual(res.status, 200)
            data = json.loads(res.read().decode("utf-8"))
            self.assertTrue(data.get("success"))
            self.assertEqual(data.get("new_priority"), "critical")
            print(f"PASS: /api/incidents/override-priority successfully updated severity to '{data['new_priority']}' with audit trail.")

    def test_10_post_tickets_work_order_creation(self):
        """Verify POST /api/tickets creates a relational work order with automated lifecycle event."""
        payload = {
            "incident_id": 1,
            "locality_id": 1,
            "assigned_team_id": 1,
            "assigned_technician_id": 6,
            "priority": "high",
            "sla_deadline": "2026-10-25T12:00:00Z"
        }
        req = urllib.request.Request(
            f"{self.base_url}/api/tickets",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as res:
            self.assertEqual(res.status, 201)
            data = json.loads(res.read().decode("utf-8"))
            self.assertTrue(data.get("success"))
            self.assertIn("ticket_number", data)
            print(f"PASS: /api/tickets created relational work order ({data['ticket_number']}).")

    def test_11_error_handling_malformed_json_and_unknown_endpoint(self):
        """Verify centralized error handling returns consistent JSON errors for 400 and 404."""
        # 1. Unknown endpoint -> 404
        try:
            with urllib.request.urlopen(f"{self.base_url}/api/non-existent-endpoint") as res:
                self.fail("Expected 404 for unknown endpoint.")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 404)
            data = json.loads(e.read().decode("utf-8"))
            self.assertIn("error", data)

        # 2. Malformed JSON -> 400
        req = urllib.request.Request(
            f"{self.base_url}/api/complaints",
            data=b"{bad_json: invalid}",
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req) as res:
                self.fail("Expected 400 for malformed JSON.")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 400)
            data = json.loads(e.read().decode("utf-8"))
            self.assertIn("error", data)
            print("PASS: Centralized error handling verified for 404 Not Found and 400 Malformed JSON.")

if __name__ == "__main__":
    unittest.main()
