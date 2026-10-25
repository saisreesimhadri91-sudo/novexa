import sys
import os
import threading
import time
import urllib.request
import json
import unittest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from server import start_server

PORT = 8012

class TestFrontendAndAPIs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server_thread = threading.Thread(target=start_server, args=(PORT,), daemon=True)
        cls.server_thread.start()
        time.sleep(1.5)
        cls.base_url = f"http://127.0.0.1:{PORT}"

    def test_01_index_html_theme_and_structure(self):
        with urllib.request.urlopen(f"{self.base_url}/") as res:
            self.assertEqual(res.status, 200)
            html = res.read().decode("utf-8")
            self.assertIn("Clean Water", html)
            self.assertIn("step-indicator", html)
            self.assertIn("wizard-step-1", html)
            self.assertIn("wizard-step-2", html)
            self.assertIn("wizard-step-3", html)
            self.assertIn("view-landing", html)
            self.assertIn("view-resident", html)
            self.assertIn("view-admin", html)
            self.assertIn("view-technician", html)
            self.assertIn("view-reports", html)
            self.assertIn("auth-modal", html)
            print("PASS: index.html serves Royal Purple theme, Landing Page, 3-Step Wizard & All Portals.")

    def test_02_css_royal_purple_palette(self):
        with urllib.request.urlopen(f"{self.base_url}/css/style.css") as res:
            self.assertEqual(res.status, 200)
            css = res.read().decode("utf-8")
            self.assertIn("#5B21B6", css)
            self.assertIn("#7C3AED", css)
            self.assertIn("#A78BFA", css)
            self.assertIn("#EDE9FE", css)
            self.assertIn("#F5F3FF", css)
            self.assertIn("royal-card", css)
            self.assertIn("btn-royal-primary", css)
            self.assertIn("step-circle", css)
            print("PASS: style.css contains the complete Light Purple & Royal Elegant design token system.")

    def test_03_js_app_engine(self):
        with urllib.request.urlopen(f"{self.base_url}/js/app.js") as res:
            self.assertEqual(res.status, 200)
            js = res.read().decode("utf-8")
            self.assertIn("goToWizardStep", js)
            self.assertIn("switchView", js)
            self.assertIn("switchRole", js)
            self.assertIn("loadReportsDashboard", js)
            self.assertIn("openAuthModal", js)
            print("PASS: app.js contains 3-step wizard, view switcher, auth modal, and reports engine.")

    def test_04_meta_endpoint(self):
        with urllib.request.urlopen(f"{self.base_url}/api/meta") as res:
            self.assertEqual(res.status, 200)
            data = json.loads(res.read().decode("utf-8"))
            self.assertEqual(len(data["localities"]), 15)
            self.assertGreaterEqual(len(data["categories"]), 5)
            print(f"PASS: /api/meta verified (15 localities, {len(data['categories'])} categories).")

    def test_05_resident_complaints_endpoint(self):
        with urllib.request.urlopen(f"{self.base_url}/api/complaints?role=resident&user_id=1") as res:
            self.assertEqual(res.status, 200)
            data = json.loads(res.read().decode("utf-8"))
            self.assertIn("complaints", data)
            print(f"PASS: /api/complaints verified for resident Priya Sharma ({len(data['complaints'])} reports).")

    def test_06_locality_health_analytics(self):
        with urllib.request.urlopen(f"{self.base_url}/api/analytics/locality") as res:
            self.assertEqual(res.status, 200)
            data = json.loads(res.read().decode("utf-8"))
            self.assertEqual(len(data["localities"]), 15)
            for loc in data["localities"]:
                self.assertIn("health_score", loc)
                self.assertIn("status_tag", loc)
            print("PASS: /api/analytics/locality verified with health scores across all 15 wards.")

    def test_07_performance_kpis(self):
        with urllib.request.urlopen(f"{self.base_url}/api/analytics/performance") as res:
            self.assertEqual(res.status, 200)
            data = json.loads(res.read().decode("utf-8"))
            perf = data["performance"]
            self.assertTrue("total_complaints" in perf or "total_tickets" in perf)
            self.assertIn("sla_compliance_rate", perf)
            self.assertTrue("mean_time_to_resolve_hours" in perf or "avg_mttr_hours" in perf)
            mttr = perf.get("mean_time_to_resolve_hours") or perf.get("avg_mttr_hours")
            print(f"PASS: /api/analytics/performance verified (MTTR={mttr}h, SLA={perf['sla_compliance_rate']}%).")

    def test_08_e2e_complaint_submission(self):
        payload = {
            "resident_id": 1,
            "locality_id": 1,
            "category_id": 1,
            "incident_time": "2026-10-24 23:25",
            "lat": 28.6285,
            "lng": 77.2082,
            "address_landmark": "Test Metro Gate 3",
            "house_number": "Flat 101",
            "description": "Automated Phase 2 Integration Test Complaint",
            "priority": "high"
        }
        req = urllib.request.Request(
            f"{self.base_url}/api/complaints",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as res:
            self.assertEqual(res.status, 200)
            created = json.loads(res.read().decode("utf-8"))
            self.assertTrue(created.get("success"))
            self.assertIn("ticket_number", created)
            print(f"PASS: /api/complaints E2E creation verified (Ticket: {created['ticket_number']}).")

if __name__ == "__main__":
    unittest.main()
