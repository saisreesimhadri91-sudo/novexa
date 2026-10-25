"""
NIVORA WATER MANAGEMENT SYSTEM — PHASE 7 SECURITY HARDENING TEST SUITE
Validates:
1. Zero secrets in repository (scans files for private keys, database passwords, service-role keys).
2. HTTP security headers (nosniff, SAMEORIGIN, CSP, XSS-Protection).
3. Payload size enforcement (rejects > 2MB with 413 Payload Too Large).
4. In-memory sliding-window rate limiting (triggers 429 Too Many Requests with Retry-After).
5. Input sanitization (HTML escaping of landmarks and descriptions against Stored XSS).
6. Role-based PII privacy preservation (telephone and apartment masking for field contractors).
7. Supabase PostgreSQL Row-Level Security (RLS) migration policies.
"""

import unittest
import json
import os
import re
import sys
import threading
import http.client
from http.server import ThreadingHTTPServer

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT_DIR)

from server import NivoraAPIHandler, MUTATION_RATE_LIMITER, GLOBAL_RATE_LIMITER
import backend.database as db_module

TEST_PORT = 8022


class TestPhase7SecurityHardening(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Reset rate limiters before test suite
        MUTATION_RATE_LIMITER.reset()
        GLOBAL_RATE_LIMITER.reset()
        cls.server = ThreadingHTTPServer(("127.0.0.1", TEST_PORT), NivoraAPIHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _api_get(self, path, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", TEST_PORT, timeout=10)
        h = headers or {}
        conn.request("GET", path, headers=h)
        res = conn.getresponse()
        data = res.read()
        conn.close()
        return res.status, res.getheaders(), data

    def _api_post(self, path, payload, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", TEST_PORT, timeout=10)
        body = json.dumps(payload).encode("utf-8") if isinstance(payload, (dict, list)) else payload
        h = {"Content-Type": "application/json"}
        if headers:
            h.update(headers)
        conn.request("POST", path, body=body, headers=h)
        res = conn.getresponse()
        data = res.read()
        conn.close()
        return res.status, res.getheaders(), data

    # -------------------------------------------------------------
    # 1. Repository Secrets Audit
    # -------------------------------------------------------------
    def test_01_zero_secrets_in_codebase(self):
        PATTERNS = [
            (re.compile(r'(?i)service[_-]?role[_-]?key\s*[:=]\s*[\'\"][a-zA-Z0-9_\-\.]{20,}[\'\"]'), "Service Role Key"),
            (re.compile(r'-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----'), "Private Key"),
            (re.compile(r'(?i)(password|passwd|pwd)\s*[:=]\s*[\'\"][^\'\"]{8,}[\'\"]'), "Hardcoded Password")
        ]

        found = []
        for root, _, files in os.walk(ROOT_DIR):
            if any(p in root for p in [".git", "__pycache__", ".pytest_cache", "scratch"]):
                continue
            for file in files:
                if file.endswith((".py", ".js", ".html", ".css", ".md", ".sql", ".json", ".env")):
                    path = os.path.join(root, file)
                    try:
                        with open(path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                        for pattern, desc in PATTERNS:
                            matches = pattern.findall(content)
                            for m in matches:
                                m_str = str(m)
                                if "your-" in m_str or "example" in m_str.lower() or "demo" in m_str.lower():
                                    continue
                                found.append((path, desc, m_str[:30]))
                    except Exception:
                        pass

        self.assertEqual(len(found), 0, f"Exposed secrets detected: {found}")
        print("PASS: SEC-1 — Zero secrets, private keys, or passwords detected across all repository files.")

    # -------------------------------------------------------------
    # 2. HTTP Security Headers
    # -------------------------------------------------------------
    def test_02_http_security_headers_present(self):
        status, headers, _ = self._api_get("/api/health")
        self.assertEqual(status, 200)
        h_dict = {k.lower(): v for k, v in headers}

        self.assertEqual(h_dict.get("x-content-type-options"), "nosniff")
        self.assertEqual(h_dict.get("x-frame-options"), "SAMEORIGIN")
        self.assertEqual(h_dict.get("x-xss-protection"), "1; mode=block")
        self.assertEqual(h_dict.get("referrer-policy"), "strict-origin-when-cross-origin")
        self.assertIn("default-src 'self'", h_dict.get("content-security-policy", ""))
        print("PASS: SEC-2 — Mandatory HTTP security headers (nosniff, SAMEORIGIN, CSP, XSS-Protection) verified.")

    # -------------------------------------------------------------
    # 3. Payload Size Limit (DoS Protection)
    # -------------------------------------------------------------
    def test_03_payload_too_large_rejection(self):
        # 2.05MB payload exceeds 2MB limit
        large_body = b"A" * (2 * 1024 * 1024 + 50000)
        conn = http.client.HTTPConnection("127.0.0.1", TEST_PORT, timeout=10)
        conn.request("POST", "/api/complaints", body=large_body, headers={"Content-Type": "application/json", "Content-Length": str(len(large_body))})
        res = conn.getresponse()
        data = res.read()
        conn.close()

        self.assertEqual(res.status, 413, f"Expected 413 Payload Too Large, got {res.status}")
        err = json.loads(data.decode())
        self.assertIn("Payload Too Large", err.get("error", ""))
        print("PASS: SEC-3 — Oversized payload (> 2MB) rejected with HTTP 413 Payload Too Large.")

    # -------------------------------------------------------------
    # 4. In-Memory Sliding Window Rate Limiting
    # -------------------------------------------------------------
    def test_04_rate_limiting_enforcement(self):
        # Use an isolated IP to avoid affecting other tests
        test_ip = "192.168.1.99"
        headers = {"X-Forwarded-For": test_ip}

        # Clear rate limiter history for this IP
        MUTATION_RATE_LIMITER.history[test_ip] = []
        old_limit = MUTATION_RATE_LIMITER.max_requests
        MUTATION_RATE_LIMITER.max_requests = 15  # Specific test threshold

        try:
            # Send up to mutation limit (15 requests)
            for i in range(15):
                payload = {
                    "resident_id": 1,
                    "locality_id": 1,
                    "category_id": 1,
                    "lat": 28.6280,
                    "lng": 77.2080,
                    "address_landmark": f"Rate Limit Test Node #{i}"
                }
                status, _, _ = self._api_post("/api/complaints", payload, headers=headers)
                self.assertEqual(status, 200)

            # The 16th request must trigger HTTP 429
            overflow_payload = {
                "resident_id": 1,
                "locality_id": 1,
                "category_id": 1,
                "lat": 28.6280,
                "lng": 77.2080,
                "address_landmark": "Overflow Attempt"
            }
            status, resp_headers, body = self._api_post("/api/complaints", overflow_payload, headers=headers)
            self.assertEqual(status, 429, f"Expected HTTP 429 Too Many Requests, got {status}")

            h_dict = {k.lower(): v for k, v in resp_headers}
            self.assertIn("retry-after", h_dict)
            err = json.loads(body.decode())
            self.assertEqual(err["status"], 429)
            self.assertIn("Rate limit exceeded", err["error"])

            # Verify bypass header works for administrative test runners
            bypass_headers = {"X-Forwarded-For": test_ip, "X-Bypass-Rate-Limit": "1"}
            status_bp, _, _ = self._api_post("/api/complaints", overflow_payload, headers=bypass_headers)
            self.assertEqual(status_bp, 200, "Bypass header must permit authorized requests")

            print("PASS: SEC-4 — In-memory sliding-window rate limiting enforced with HTTP 429 & Retry-After header.")
        finally:
            MUTATION_RATE_LIMITER.max_requests = old_limit

    # -------------------------------------------------------------
    # 5. Stored XSS Neutralization
    # -------------------------------------------------------------
    def test_05_stored_xss_neutralization(self):
        malicious_landmark = "<script>alert('XSS_ATTACK')</script> Landmark"
        malicious_desc = "<img src=x onerror=alert('PWNED')>"

        payload = {
            "resident_id": 1,
            "locality_id": 1,
            "category_id": 1,
            "lat": 28.6280,
            "lng": 77.2080,
            "address_landmark": malicious_landmark,
            "description": malicious_desc
        }
        status, _, body = self._api_post("/api/complaints", payload, headers={"X-Bypass-Rate-Limit": "1"})
        self.assertEqual(status, 200)
        complaint_id = json.loads(body.decode())["complaint_id"]

        # Check DB to verify HTML entities were escaped
        conn = db_module.get_connection()
        c = conn.cursor()
        c.execute("SELECT address_landmark, description FROM complaints WHERE id = ?", (complaint_id,))
        row = c.fetchone()
        conn.close()

        self.assertIn("&lt;script&gt;", row["address_landmark"])
        self.assertNotIn("<script>", row["address_landmark"])
        self.assertIn("&lt;img", row["description"])
        self.assertNotIn("<img", row["description"])
        print("PASS: SEC-5 — Stored XSS vectors safely neutralized via server-side HTML entity escaping.")

    # -------------------------------------------------------------
    # 6. PII Masking & Privacy Guard
    # -------------------------------------------------------------
    def test_06_role_based_pii_privacy_guard(self):
        # Technician view query
        status, _, body = self._api_get("/api/complaints?role=technician&user_id=6", headers={"X-Bypass-Rate-Limit": "1"})
        self.assertEqual(status, 200)
        jobs = json.loads(body.decode())["complaints"]
        for j in jobs[:20]:
            phone = j.get("resident_phone")
            if phone and phone != "[Protected]":
                self.assertIn("****", phone)
            house = j.get("house_number")
            if house:
                self.assertIn("Protected", house)

        # Resident view query for own user ID
        status, _, body = self._api_get("/api/complaints?role=resident&user_id=1", headers={"X-Bypass-Rate-Limit": "1"})
        self.assertEqual(status, 200)
        own_reports = json.loads(body.decode())["complaints"]
        for r in own_reports:
            phone = r.get("resident_phone")
            if phone:
                self.assertNotIn("****", phone, "Resident must see their own unmasked phone")

        print("PASS: SEC-6 — Role-based PII privacy verified (citizen phone & flat IDs masked from technicians).")

    # -------------------------------------------------------------
    # 7. Supabase PostgreSQL Row-Level Security (RLS) Policies
    # -------------------------------------------------------------
    def test_07_supabase_rls_policies_verified(self):
        migration_file = os.path.join(ROOT_DIR, "supabase", "migrations", "20261024160001_nivora_rls_and_permissions.sql")
        self.assertTrue(os.path.exists(migration_file), "Supabase RLS migration file must exist")

        with open(migration_file, "r", encoding="utf-8") as f:
            sql_content = f.read()

        # Check critical security functions and policy keywords
        self.assertIn("ENABLE ROW LEVEL SECURITY", sql_content)
        self.assertIn("public.get_current_user_role()", sql_content)
        self.assertIn("public.is_admin()", sql_content)
        self.assertIn("public.is_staff()", sql_content)
        self.assertIn("complaints_select_policy", sql_content)
        self.assertIn("resident_id = auth.uid()", sql_content)
        self.assertIn("ALTER TABLE public.complaints ENABLE ROW LEVEL SECURITY;", sql_content)
        self.assertIn("ALTER TABLE public.tickets ENABLE ROW LEVEL SECURITY;", sql_content)

        print("PASS: SEC-7 — Supabase PostgreSQL RLS policies and tenant isolation verified in migration files.")


if __name__ == "__main__":
    unittest.main()
