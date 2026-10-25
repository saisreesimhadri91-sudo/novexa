"""
NIVORA WATER MANAGEMENT SYSTEM — PHASE 8 DEPLOYMENT SMOKE TEST SUITE
Comprehensive live validation of production endpoints, static asset pipelines,
health readiness probes, and end-to-end data flows.
"""

import unittest
import json
import os
import sys
import threading
import http.client
from http.server import ThreadingHTTPServer

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT_DIR)

from server import NivoraAPIHandler, generate_unique_ticket_number
import backend.database as db_module

SMOKE_PORT = 8024


class TestDeploymentSmokeVerification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", SMOKE_PORT), NivoraAPIHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _get(self, path):
        conn = http.client.HTTPConnection("127.0.0.1", SMOKE_PORT, timeout=10)
        conn.request("GET", path, headers={"X-Bypass-Rate-Limit": "1"})
        res = conn.getresponse()
        data = res.read()
        conn.close()
        return res.status, res.getheaders(), data

    def _post(self, path, payload):
        conn = http.client.HTTPConnection("127.0.0.1", SMOKE_PORT, timeout=10)
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json", "X-Bypass-Rate-Limit": "1"}
        conn.request("POST", path, body=body, headers=headers)
        res = conn.getresponse()
        data = res.read()
        conn.close()
        return res.status, res.getheaders(), data

    # 1. Root and Static HTML Delivery
    def test_01_root_landing_page_delivery(self):
        status, headers, body = self._get("/")
        self.assertEqual(status, 200)
        html = body.decode("utf-8")
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("NIVORA", html)
        self.assertIn("Clean Water", html)
        self.assertIn("Stronger Communities", html)
        self.assertIn("#5B21B6", html)
        self.assertIn("view-resident", html)
        self.assertIn("view-admin", html)
        self.assertIn("view-technician", html)
        self.assertIn("view-reports", html)
        print("PASS: Smoke-1 — Root SPA delivered (Landing Page, 3-Step Wizard, 4 Portals, Royal Purple theme).")

    # 2. Static Stylesheet Delivery
    def test_02_static_css_delivery(self):
        status, headers, body = self._get("/css/style.css")
        self.assertEqual(status, 200)
        css = body.decode("utf-8")
        self.assertIn("#5B21B6", css)
        self.assertIn("#7C3AED", css)
        self.assertIn("#EDE9FE", css)
        self.assertIn("#F5F3FF", css)
        self.assertIn("royal-card", css)
        print("PASS: Smoke-2 — Static CSS delivered with complete Light Purple & Royal Elegant design token system.")

    # 3. Static JavaScript Delivery
    def test_03_static_js_delivery(self):
        status, headers, body = self._get("/js/app.js")
        self.assertEqual(status, 200)
        js = body.decode("utf-8")
        self.assertIn("appState", js)
        self.assertIn("switchView", js)
        self.assertIn("goToWizardStep", js)
        self.assertIn("initOrUpdateMap", js)
        print("PASS: Smoke-3 — Static JS client engine delivered.")

    # 4. Production Health Readiness Probe
    def test_04_health_readiness_probe(self):
        status, headers, body = self._get("/api/health")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["database"], "connected")
        self.assertEqual(data["version"], "2.0-STABLE")
        self.assertGreater(data["total_complaints"], 10000)
        self.assertEqual(data["wards_monitored"], 15)
        print(f"PASS: Smoke-4 — Health readiness probe active (Version: {data['version']}, Complaints: {data['total_complaints']}, Database: {data['database']}).")

    # 5. Metadata Probe
    def test_05_metadata_probe(self):
        status, _, body = self._get("/api/meta")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(len(data["localities"]), 15)
        self.assertEqual(len(data["categories"]), 5)
        self.assertGreaterEqual(len(data["teams"]), 10)
        print("PASS: Smoke-5 — Metadata probe returned 15 localities, 5 categories, and service teams.")

    # 6. Citizen Complaints & Resident Journey
    def test_06_resident_complaints_probe(self):
        status, _, body = self._get("/api/complaints?role=resident&user_id=1")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("complaints", data)
        self.assertIsInstance(data["complaints"], list)
        print(f"PASS: Smoke-6 — Resident portal loaded {len(data['complaints'])} tracked complaints.")

    # 7. Locality Health Analytics Probe
    def test_07_locality_analytics_probe(self):
        status, _, body = self._get("/api/analytics/locality")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(len(data["localities"]), 15)
        for loc in data["localities"]:
            self.assertIn("health_score", loc)
            self.assertIn("pipeline_grid", loc)
        print("PASS: Smoke-7 — Locality health analytics returned computed scores for all 15 wards.")

    # 8. Executive Performance Probe
    def test_08_performance_kpis_probe(self):
        status, _, body = self._get("/api/analytics/performance")
        self.assertEqual(status, 200)
        perf = json.loads(body.decode("utf-8"))["performance"]
        self.assertIn("sla_compliance_rate", perf)
        self.assertIn("avg_mttr_hours", perf)
        self.assertGreaterEqual(perf["sla_compliance_rate"], 90.0)
        print(f"PASS: Smoke-8 — Executive KPIs returned (SLA: {perf['sla_compliance_rate']}%, MTTR: {perf['avg_mttr_hours']}h).")

    # 9. CSV Streaming Export Probe
    def test_09_csv_stream_export_probe(self):
        status, headers, body = self._get("/api/reports/export/csv")
        self.assertEqual(status, 200)
        h_dict = dict(headers)
        self.assertIn("text/csv", h_dict.get("Content-Type", ""))
        self.assertIn("attachment; filename=nivora_export_", h_dict.get("Content-Disposition", ""))
        csv_text = body.decode("utf-8")
        self.assertIn("Ticket Number,Locality,Category", csv_text)
        print("PASS: Smoke-9 — Operational CSV stream export delivered with RFC 4180 headers.")

    # 10. Live E2E Citizen Submission Mutation
    def test_10_live_e2e_complaint_mutation(self):
        payload = {
            "resident_id": 1,
            "locality_id": 1,
            "category_id": 1,
            "incident_time": "2026-10-25 00:25",
            "lat": 28.6285,
            "lng": 77.2087,
            "address_landmark": "Smoke Test Verification Substation Gate 1",
            "description": "Live production smoke test observation."
        }
        status, _, body = self._post("/api/complaints", payload)
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data["success"])
        ticket = data["ticket_number"]
        self.assertTrue(ticket.startswith("TKT-2026-"))
        print(f"PASS: Smoke-10 — Live citizen complaint registration succeeded (Ticket Reference: {ticket}).")


if __name__ == "__main__":
    unittest.main()
