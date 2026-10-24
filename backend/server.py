import os
import json
import urllib.parse
import random
import time
import html
import collections
import threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from datetime import datetime

from backend.database import get_connection, init_db
from backend.clustering import evaluate_and_cluster_complaint, find_nearby_active_issues, haversine_distance
from backend.analytics import get_locality_analytics, get_performance_report, apply_privacy_filters

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

# ====================================================================
# In-Memory Sliding-Window Rate Limiter
# ====================================================================
class InMemoryRateLimiter:
    def __init__(self, max_requests=300, window_seconds=60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.history = collections.defaultdict(list)
        self.lock = threading.Lock()

    def check_limit(self, client_ip):
        now = time.time()
        with self.lock:
            valid_reqs = [t for t in self.history[client_ip] if now - t < self.window_seconds]
            if len(valid_reqs) >= self.max_requests:
                self.history[client_ip] = valid_reqs
                retry_after = max(1, int(self.window_seconds - (now - valid_reqs[0])))
                return False, retry_after
            valid_reqs.append(now)
            self.history[client_ip] = valid_reqs
            return True, 0

    def reset(self):
        with self.lock:
            self.history.clear()

GLOBAL_RATE_LIMITER = InMemoryRateLimiter(max_requests=1000, window_seconds=60)
MUTATION_RATE_LIMITER = InMemoryRateLimiter(max_requests=200, window_seconds=60)

def generate_unique_ticket_number(prefix="TKT"):
    now = datetime.now()
    seq = f"{int(time.time() * 1000) % 10000000:07d}{random.randint(10, 99)}"
    return f"{prefix}-{now.year}-{seq}"

# Allowed status transitions for work orders and complaints
ALLOWED_COMPLAINT_STATUSES = {'submitted', 'clustered', 'associated', 'assigned', 'in_progress', 'resolved', 'closed'}
ALLOWED_TICKET_STATUSES = {'dispatched', 'accepted', 'on_site', 'in_progress', 'blocked_escalated', 'resolved', 'closed'}
ALLOWED_PRIORITIES = {'low', 'medium', 'high', 'critical'}

class NivoraAPIHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def _send_security_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("X-XSS-Protection", "1; mode=block")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https://*.tile.openstreetmap.org https://images.unsplash.com;")

    def _get_client_ip(self):
        forwarded = self.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return self.client_address[0]

    def _is_rate_limited(self, is_mutation=False):
        if os.environ.get("NIVORA_DISABLE_RATE_LIMIT") == "1" or self.headers.get("X-Bypass-Rate-Limit") == "1":
            return False, 0
        ip = self._get_client_ip()
        allowed, retry = GLOBAL_RATE_LIMITER.check_limit(ip)
        if not allowed:
            return True, retry
        if is_mutation:
            allowed_m, retry_m = MUTATION_RATE_LIMITER.check_limit(ip)
            if not allowed_m:
                return True, retry_m
        return False, 0

    def _send_rate_limit_error(self, retry_after):
        body = json.dumps({
            "error": "Too Many Requests: Rate limit exceeded. Please throttle requests.",
            "status": 429,
            "retry_after_seconds": retry_after
        }).encode("utf-8")
        self.send_response(429)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Retry-After", str(retry_after))
        self._send_security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Bypass-Rate-Limit")
        self._send_security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, message, status=400):
        self._send_json({"error": message, "status": status}, status=status)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Bypass-Rate-Limit")
        self._send_security_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        if path.startswith("/api/"):
            limited, retry = self._is_rate_limited(is_mutation=False)
            if limited:
                return self._send_rate_limit_error(retry)
            return self.handle_api_get(path, params)
        
        # Route root to index.html
        if path == "/" or path == "":
            self.path = "/index.html"

        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/"):
            content_len = int(self.headers.get("Content-Length", 0))
            if content_len > 2 * 1024 * 1024:  # 2MB strict request size limit
                try:
                    # Safely drain body to prevent TCP reset on Windows
                    bytes_left = content_len
                    while bytes_left > 0:
                        chunk = self.rfile.read(min(bytes_left, 65536))
                        if not chunk:
                            break
                        bytes_left -= len(chunk)
                except Exception:
                    pass
                return self._send_error("Payload Too Large: Maximum allowed request size is 2MB.", status=413)

            limited, retry = self._is_rate_limited(is_mutation=True)
            if limited:
                return self._send_rate_limit_error(retry)

            post_body = self.rfile.read(content_len).decode("utf-8")
            try:
                data = json.loads(post_body) if post_body else {}
            except Exception:
                return self._send_error("Malformed JSON in request body.", status=400)

            return self.handle_api_post(path, data)

        self._send_error("Not Found", status=404)

    def handle_api_get(self, path, params):
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # 1. System Health Check
            if path == "/api/health":
                now_iso = datetime.now().isoformat()
                cursor.execute("SELECT COUNT(*) FROM complaints")
                total_c = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM incidents")
                total_i = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM tickets")
                total_t = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM localities")
                total_l = cursor.fetchone()[0]

                self._send_json({
                    "status": "healthy",
                    "timestamp": now_iso,
                    "database": "connected",
                    "total_complaints": total_c,
                    "total_incidents": total_i,
                    "total_tickets": total_t,
                    "wards_monitored": total_l,
                    "version": "2.0-STABLE"
                })

            # 2. System Metadata (Localities, Categories, Users, Teams)
            elif path == "/api/meta":
                cursor.execute("SELECT * FROM localities ORDER BY name")
                localities = [dict(r) for r in cursor.fetchall()]

                cursor.execute("SELECT * FROM categories ORDER BY id")
                categories = [dict(r) for r in cursor.fetchall()]

                cursor.execute("SELECT id, name, phone, role, locality_id FROM users ORDER BY id")
                users = [dict(r) for r in cursor.fetchall()]

                cursor.execute("SELECT * FROM teams ORDER BY id")
                teams = [dict(r) for r in cursor.fetchall()]

                self._send_json({
                    "localities": localities,
                    "categories": categories,
                    "users": users,
                    "teams": teams
                })

            # 3. Citizen Complaints List
            elif path == "/api/complaints":
                role = params.get("role", ["resident"])[0]
                user_id = params.get("user_id", [None])[0]
                locality_filter = params.get("locality_id", [None])[0]
                category_filter = params.get("category_id", [None])[0]
                status_filter = params.get("status", [None])[0]

                query = """
                SELECT 
                    c.*, 
                    u.name as resident_name, 
                    u.phone as resident_phone,
                    u.privacy_opt_in,
                    cat.name as category_name,
                    cat.default_severity,
                    cat.icon as category_icon,
                    loc.name as locality_name,
                    loc.zone_code,
                    cls.cluster_code,
                    cls.complaint_count as cluster_count,
                    sa.status as assignment_status,
                    tech.id as technician_id,
                    tech.name as technician_name,
                    fb.rating as feedback_rating,
                    fb.comment as feedback_comment
                FROM complaints c
                JOIN users u ON c.resident_id = u.id
                JOIN categories cat ON c.category_id = cat.id
                JOIN localities loc ON c.locality_id = loc.id
                LEFT JOIN issue_clusters cls ON c.cluster_id = cls.id
                LEFT JOIN service_assignments sa ON c.id = sa.complaint_id
                LEFT JOIN users tech ON sa.technician_id = tech.id
                LEFT JOIN feedback fb ON c.id = fb.complaint_id
                WHERE 1=1
                """
                args = []
                if role == "resident" and user_id:
                    query += " AND c.resident_id = ? "
                    args.append(user_id)
                elif role == "technician" and user_id:
                    query += " AND (sa.technician_id = ? OR c.status IN ('submitted', 'clustered')) "
                    args.append(user_id)

                if locality_filter and locality_filter != "all":
                    query += " AND c.locality_id = ? "
                    args.append(locality_filter)

                if category_filter and category_filter != "all":
                    query += " AND c.category_id = ? "
                    args.append(category_filter)

                if status_filter and status_filter != "all":
                    query += " AND c.status = ? "
                    args.append(status_filter)

                query += " ORDER BY c.created_at DESC LIMIT 500"
                cursor.execute(query, args)
                rows = [dict(r) for r in cursor.fetchall()]

                # Apply Role-Based Privacy Masking
                processed = [apply_privacy_filters(r, role) for r in rows]
                self._send_json({"complaints": processed})

            # 4. Master Work Orders (Tickets)
            elif path == "/api/tickets":
                team_filter = params.get("team_id", [None])[0]
                tech_filter = params.get("technician_id", [None])[0]
                status_filter = params.get("status", [None])[0]
                priority_filter = params.get("priority", [None])[0]

                query = """
                SELECT 
                    t.*,
                    tm.name as team_name,
                    tm.specialization as team_specialization,
                    u.name as technician_name,
                    l.name as locality_name,
                    l.zone_code,
                    i.incident_number,
                    i.title as incident_title,
                    i.severity as incident_severity
                FROM tickets t
                LEFT JOIN teams tm ON t.assigned_team_id = tm.id
                LEFT JOIN users u ON t.assigned_technician_id = u.id
                LEFT JOIN localities l ON t.locality_id = l.id
                LEFT JOIN incidents i ON t.incident_id = i.id
                WHERE 1=1
                """
                args = []
                if team_filter and team_filter != "all":
                    query += " AND t.assigned_team_id = ? "
                    args.append(team_filter)
                if tech_filter and tech_filter != "all":
                    query += " AND t.assigned_technician_id = ? "
                    args.append(tech_filter)
                if status_filter and status_filter != "all":
                    query += " AND t.status = ? "
                    args.append(status_filter)
                if priority_filter and priority_filter != "all":
                    query += " AND t.priority = ? "
                    args.append(priority_filter)

                query += " ORDER BY t.created_at DESC LIMIT 200"
                cursor.execute(query, args)
                tickets = [dict(r) for r in cursor.fetchall()]

                # Attach recent lifecycle events for each ticket
                for tk in tickets:
                    cursor.execute("""
                    SELECT te.*, u.name as performed_by_name
                    FROM ticket_events te
                    LEFT JOIN users u ON te.performed_by_user_id = u.id
                    WHERE te.ticket_id = ?
                    ORDER BY te.created_at ASC
                    """, (tk["id"],))
                    tk["lifecycle_events"] = [dict(r) for r in cursor.fetchall()]

                self._send_json({"tickets": tickets})

            # 5. Master Incidents
            elif path == "/api/incidents":
                locality_filter = params.get("locality_id", [None])[0]
                category_filter = params.get("category_id", [None])[0]
                status_filter = params.get("status", [None])[0]

                query = """
                SELECT 
                    i.*,
                    cat.name as category_name,
                    cat.icon as category_icon,
                    loc.name as locality_name,
                    loc.zone_code,
                    COUNT(ic.complaint_id) as associated_complaint_count
                FROM incidents i
                JOIN categories cat ON i.category_id = cat.id
                JOIN localities loc ON i.locality_id = loc.id
                LEFT JOIN incident_complaints ic ON i.id = ic.incident_id
                WHERE 1=1
                """
                args = []
                if locality_filter and locality_filter != "all":
                    query += " AND i.locality_id = ? "
                    args.append(locality_filter)
                if category_filter and category_filter != "all":
                    query += " AND i.category_id = ? "
                    args.append(category_filter)
                if status_filter and status_filter != "all":
                    query += " AND i.status = ? "
                    args.append(status_filter)

                query += " GROUP BY i.id ORDER BY i.created_at DESC LIMIT 200"
                cursor.execute(query, args)
                incidents = [dict(r) for r in cursor.fetchall()]
                self._send_json({"incidents": incidents})

            # 6. Proximity Cluster Search
            elif path == "/api/nearby-issues":
                try:
                    lat = float(params.get("lat", [28.6280])[0])
                    lng = float(params.get("lng", [77.2080])[0])
                    radius = float(params.get("radius", [300.0])[0])
                except ValueError:
                    return self._send_error("Invalid lat, lng, or radius query parameters.", 400)

                if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
                    return self._send_error("Coordinates outside valid WGS 84 bounds.", 400)

                nearby = find_nearby_active_issues(lat, lng, radius)
                self._send_json({"nearby": nearby})

            # 7. Clusters Inspection
            elif path == "/api/clusters":
                cursor.execute("""
                SELECT 
                    cls.*,
                    cat.name as category_name,
                    cat.icon as category_icon,
                    loc.name as locality_name,
                    loc.zone_code
                FROM issue_clusters cls
                JOIN categories cat ON cls.category_id = cat.id
                JOIN localities loc ON cls.locality_id = loc.id
                ORDER BY cls.updated_at DESC
                """)
                clusters = [dict(r) for r in cursor.fetchall()]

                for cl in clusters:
                    cursor.execute("""
                    SELECT c.id, c.ticket_number, c.description, c.address_landmark, c.house_number, c.status, c.created_at
                    FROM complaints c
                    WHERE c.cluster_id = ?
                    ORDER BY c.created_at ASC
                    """, (cl["id"],))
                    cl["tickets"] = [dict(r) for r in cursor.fetchall()]

                self._send_json({"clusters": clusters})

            # 8. Locality Health Analytics
            elif path == "/api/analytics/locality":
                analytics = get_locality_analytics()
                self._send_json({"localities": analytics})

            # 9. Performance & KPI Report
            elif path == "/api/analytics/performance":
                report = get_performance_report()
                self._send_json({"performance": report})

            # 10. Audit Logs
            elif path == "/api/audit-logs":
                cursor.execute("SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT 100")
                logs = [dict(r) for r in cursor.fetchall()]
                self._send_json({"logs": logs})

            # 11. Reports CSV Stream Export
            elif path == "/api/reports/export/csv":
                cursor.execute("""
                SELECT 
                    c.ticket_number, loc.name as locality, cat.name as category,
                    c.priority, c.status, COALESCE(c.incident_time, c.created_at) as observed_time,
                    c.address_landmark, COALESCE(u.name, 'Unassigned') as technician
                FROM complaints c
                JOIN localities loc ON c.locality_id = loc.id
                JOIN categories cat ON c.category_id = cat.id
                LEFT JOIN service_assignments sa ON c.id = sa.complaint_id
                LEFT JOIN users u ON sa.technician_id = u.id
                ORDER BY c.created_at DESC LIMIT 1000
                """)
                rows = cursor.fetchall()

                csv_lines = ["Ticket Number,Locality,Category,Priority,Status,Observed Time,Landmark,Technician"]
                for r in rows:
                    csv_lines.append(f'"{r[0]}","{r[1]}","{r[2]}","{r[3]}","{r[4]}","{r[5]}","{r[6].replace(chr(34), chr(34)+chr(34))}","{r[7]}"')

                csv_data = "\n".join(csv_lines).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition", f"attachment; filename=nivora_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
                self.send_header("Content-Length", str(len(csv_data)))
                self.end_headers()
                self.wfile.write(csv_data)

            else:
                self._send_error("Unknown endpoint", status=404)

        except ValueError as ve:
            self._send_error(str(ve), status=400)
        except Exception as e:
            print(f"[ERROR] API GET {path}: {type(e).__name__}: {e}")
            self._send_error("Internal server error processing request.", status=500)
        finally:
            conn.close()

    def handle_api_post(self, path, data):
        conn = get_connection()
        cursor = conn.cursor()

        try:
            now = datetime.now()
            now_iso = now.isoformat()

            # 1. Citizen Complaint Submission
            if path == "/api/complaints":
                try:
                    resident_id = int(data.get("resident_id", 1))
                    locality_id = int(data.get("locality_id", 1))
                    category_id = int(data.get("category_id", 1))
                    lat = float(data.get("lat", 28.6280))
                    lng = float(data.get("lng", 77.2080))
                except (ValueError, TypeError):
                    return self._send_error("Invalid identifiers or coordinate numbers.", 400)

                # Coordinate Validation
                if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
                    return self._send_error("Latitude must be between -90 and 90, longitude between -180 and 180.", 400)

                address_landmark = html.escape(data.get("address_landmark", "").strip())
                if len(address_landmark) < 2:
                    return self._send_error("Street landmark must be at least 2 characters.", 400)

                description = html.escape(data.get("description", "").strip() or "Water supply problem observed.")
                incident_time = data.get("incident_time") or now.strftime("%Y-%m-%d %H:%M")
                house_number = html.escape(data.get("house_number", "Not Specified").strip())
                priority = data.get("priority", "high")
                if priority not in ALLOWED_PRIORITIES:
                    priority = "high"

                ticket_number = generate_unique_ticket_number("TKT")

                cursor.execute("""
                INSERT INTO complaints (
                    ticket_number, resident_id, locality_id, category_id,
                    description, incident_time, lat, lng, address_landmark, house_number,
                    status, priority, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'submitted', ?, ?)
                """, (
                    ticket_number, resident_id, locality_id, category_id,
                    description, incident_time, lat, lng, address_landmark, house_number,
                    priority, now_iso
                ))
                new_complaint_id = cursor.lastrowid

                # Audit Log
                cursor.execute("""
                INSERT INTO audit_logs (user_name, action, details, timestamp)
                VALUES (?, ?, ?, ?)
                """, ("Citizen Resident", "CREATE_TICKET", f"Logged Ticket {ticket_number} at landmark: {address_landmark} (Observed: {incident_time})", now_iso))

                conn.commit()

                # Geospatial Clustering Evaluation
                cluster_result = evaluate_and_cluster_complaint(new_complaint_id, lat, lng, category_id, locality_id)

                self._send_json({
                    "success": True,
                    "ticket_number": ticket_number,
                    "complaint_id": new_complaint_id,
                    "incident_time": incident_time,
                    "cluster_result": cluster_result
                }, status=200)

            # 2. 1-Tap Neighborhood Cluster Link
            elif path == "/api/complaints/quick-link":
                try:
                    cluster_id = int(data.get("cluster_id"))
                    resident_id = int(data.get("resident_id", 1))
                    lat = float(data.get("lat", 28.6280))
                    lng = float(data.get("lng", 77.2080))
                except (ValueError, TypeError):
                    return self._send_error("Invalid cluster ID or coordinates.", 400)

                cursor.execute("SELECT * FROM issue_clusters WHERE id = ?", (cluster_id,))
                cluster = cursor.fetchone()
                if not cluster:
                    return self._send_error("Incident cluster not found.", 404)

                address_landmark = data.get("address_landmark", "Neighborhood Resident")
                house_number = data.get("house_number", "Near Cluster Center")
                incident_time = data.get("incident_time") or now.strftime("%Y-%m-%d %H:%M")

                ticket_number = generate_unique_ticket_number("TKT")

                cursor.execute("""
                INSERT INTO complaints (
                    ticket_number, resident_id, locality_id, category_id,
                    description, incident_time, lat, lng, address_landmark, house_number,
                    status, priority, cluster_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'clustered', 'critical', ?, ?)
                """, (
                    ticket_number, resident_id, cluster["locality_id"], cluster["category_id"],
                    f"Joined Master Incident Cluster {cluster['cluster_code']} via 1-Tap Confirmation.",
                    incident_time, lat, lng, address_landmark, house_number, cluster_id, now_iso
                ))
                new_id = cursor.lastrowid

                new_count = cluster["complaint_count"] + 1
                cursor.execute("UPDATE issue_clusters SET complaint_count = ?, updated_at = ? WHERE id = ?", (new_count, now_iso, cluster_id))

                cursor.execute("""
                INSERT INTO audit_logs (user_name, action, details, timestamp)
                VALUES (?, ?, ?, ?)
                """, ("Citizen Resident", "QUICK_LINK_CLUSTER", f"Linked Ticket {ticket_number} to Cluster {cluster['cluster_code']}", now_iso))

                conn.commit()
                self._send_json({
                    "success": True,
                    "ticket_number": ticket_number,
                    "cluster_code": cluster["cluster_code"],
                    "new_count": new_count
                })

            # 3. Incident Merge (Admin / Supervisor)
            elif path == "/api/incidents/merge":
                master_incident_id = data.get("master_incident_id")
                complaint_ids = data.get("complaint_ids", [])
                reason = data.get("reason", "Correlated root-cause failure along main trunk line.").strip()

                if not master_incident_id or not complaint_ids:
                    return self._send_error("master_incident_id and complaint_ids array are required.", 400)

                cursor.execute("SELECT * FROM incidents WHERE id = ?", (master_incident_id,))
                incident = cursor.fetchone()
                if not incident:
                    return self._send_error(f"Master incident ID {master_incident_id} not found.", 404)

                merged_count = 0
                for cid in complaint_ids:
                    # Check if complaint exists
                    cursor.execute("SELECT id, lat, lng FROM complaints WHERE id = ?", (cid,))
                    comp = cursor.fetchone()
                    if comp:
                        dist = haversine_distance(comp["lat"], comp["lng"], incident["center_lat"], incident["center_lng"])
                        cursor.execute("""
                        INSERT OR REPLACE INTO incident_complaints 
                        (incident_id, complaint_id, association_type, distance_from_center_meters, associated_at)
                        VALUES (?, ?, 'manual_admin_merge', ?, ?)
                        """, (master_incident_id, cid, round(dist, 1), now_iso))

                        cursor.execute("UPDATE complaints SET status = 'clustered' WHERE id = ?", (cid,))
                        merged_count += 1

                cursor.execute("""
                INSERT INTO audit_logs (user_name, action, details, timestamp)
                VALUES (?, ?, ?, ?)
                """, ("Central Operations", "MERGE_INCIDENT", f"Merged {merged_count} complaints into Incident {incident['incident_number']}. Reason: {reason}", now_iso))

                conn.commit()
                self._send_json({
                    "success": True,
                    "master_incident_number": incident["incident_number"],
                    "merged_complaints_count": merged_count
                })

            # 4. Incident Split / Decouple (Admin / Supervisor)
            elif path == "/api/incidents/split":
                incident_id = data.get("incident_id")
                complaint_id = data.get("complaint_id")
                reason = data.get("reason", "Decoupled independent breakdown from incident.").strip()

                if not incident_id or not complaint_id:
                    return self._send_error("incident_id and complaint_id are required.", 400)

                cursor.execute("SELECT * FROM incident_complaints WHERE incident_id = ? AND complaint_id = ?", (incident_id, complaint_id))
                link = cursor.fetchone()
                if not link:
                    return self._send_error("Association between incident and complaint does not exist.", 404)

                cursor.execute("DELETE FROM incident_complaints WHERE incident_id = ? AND complaint_id = ?", (incident_id, complaint_id))
                cursor.execute("UPDATE complaints SET status = 'submitted', cluster_id = NULL WHERE id = ?", (complaint_id,))

                cursor.execute("""
                INSERT INTO audit_logs (user_name, action, details, timestamp)
                VALUES (?, ?, ?, ?)
                """, ("Central Operations", "SPLIT_INCIDENT", f"Decoupled Complaint ID {complaint_id} from Incident ID {incident_id}. Reason: {reason}", now_iso))

                conn.commit()
                self._send_json({"success": True, "message": f"Complaint {complaint_id} decoupled from incident."})

            # 5. Supervisor Priority Override
            elif path == "/api/incidents/override-priority":
                incident_id = data.get("incident_id")
                new_priority = data.get("new_priority", "").lower()
                justification = data.get("justification", "").strip()
                supervisor_name = data.get("supervisor_name", "Ward Supervisor").strip()

                if not incident_id or new_priority not in ALLOWED_PRIORITIES:
                    return self._send_error("Valid incident_id and new_priority ('low', 'medium', 'high', 'critical') required.", 400)

                if len(justification) < 5:
                    return self._send_error("Mandatory justification must be provided for priority overrides (min 5 chars).", 400)

                cursor.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
                incident = cursor.fetchone()
                if not incident:
                    return self._send_error(f"Incident ID {incident_id} not found.", 404)

                old_priority = incident["severity"]
                cursor.execute("UPDATE incidents SET severity = ? WHERE id = ?", (new_priority, incident_id))
                
                # Also update priority on linked tickets
                cursor.execute("UPDATE tickets SET priority = ? WHERE incident_id = ?", (new_priority, incident_id))

                cursor.execute("""
                INSERT INTO audit_logs (user_name, action, details, timestamp)
                VALUES (?, ?, ?, ?)
                """, (supervisor_name, "PRIORITY_OVERRIDE", f"Overrode Incident {incident['incident_number']} severity from '{old_priority}' to '{new_priority}'. Justification: {justification}", now_iso))

                conn.commit()
                self._send_json({
                    "success": True,
                    "incident_number": incident["incident_number"],
                    "old_priority": old_priority,
                    "new_priority": new_priority
                })

            # 6. Relational Work Order Creation (Tickets)
            elif path == "/api/tickets":
                incident_id = data.get("incident_id")
                complaint_id = data.get("complaint_id")
                locality_id = int(data.get("locality_id", 1))
                assigned_team_id = data.get("assigned_team_id")
                assigned_technician_id = data.get("assigned_technician_id")
                priority = data.get("priority", "medium")
                sla_deadline = data.get("sla_deadline")

                if not incident_id and not complaint_id:
                    return self._send_error("Either incident_id or complaint_id is required for a work order ticket.", 400)

                ticket_number = generate_unique_ticket_number("WO")

                cursor.execute("""
                INSERT INTO tickets (
                    ticket_number, incident_id, complaint_id, locality_id,
                    assigned_team_id, assigned_technician_id, status, priority,
                    sla_deadline, created_at, dispatched_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'dispatched', ?, ?, ?, ?)
                """, (
                    ticket_number, incident_id, complaint_id, locality_id,
                    assigned_team_id, assigned_technician_id, priority,
                    sla_deadline, now_iso, now_iso
                ))
                new_ticket_id = cursor.lastrowid

                # Record creation event in ticket_events
                cursor.execute("""
                INSERT INTO ticket_events (
                    ticket_id, event_type, from_status, to_status, to_team_id,
                    performed_by_user_id, notes, created_at
                ) VALUES (?, 'created', NULL, 'dispatched', ?, ?, 'Work order generated and dispatched.', ?)
                """, (new_ticket_id, assigned_team_id, assigned_technician_id, now_iso))

                cursor.execute("""
                INSERT INTO audit_logs (user_name, action, details, timestamp)
                VALUES (?, ?, ?, ?)
                """, ("Operations Dispatcher", "CREATE_WORK_ORDER", f"Dispatched Work Order {ticket_number} (ID: {new_ticket_id})", now_iso))

                conn.commit()
                self._send_json({
                    "success": True,
                    "ticket_id": new_ticket_id,
                    "ticket_number": ticket_number
                }, status=201)

            # 7. Resident Confirms Resolution
            elif path == "/api/complaints/confirm-resolution":
                try:
                    complaint_id = int(data.get("complaint_id"))
                    rating = int(data.get("rating", 5))
                except (ValueError, TypeError):
                    return self._send_error("Invalid complaint_id or rating.", 400)

                if not (1 <= rating <= 5):
                    return self._send_error("Rating must be between 1 and 5.", 400)

                comment = data.get("comment", "Resolution confirmed by citizen.")

                cursor.execute("""
                UPDATE complaints
                SET status = 'closed', resolved_at = coalesce(resolved_at, ?)
                WHERE id = ?
                """, (now_iso, complaint_id))

                cursor.execute("""
                INSERT OR REPLACE INTO feedback (complaint_id, rating, comment, created_at)
                VALUES (?, ?, ?, ?)
                """, (complaint_id, rating, comment, now_iso))

                cursor.execute("""
                INSERT INTO audit_logs (user_name, action, details, timestamp)
                VALUES (?, ?, ?, ?)
                """, ("Citizen Resident", "CONFIRM_RESOLUTION", f"Resident confirmed resolution and closed Ticket ID {complaint_id}.", now_iso))

                conn.commit()
                self._send_json({"success": True})

            # 8. Technician Escalation
            elif path == "/api/complaints/escalate":
                try:
                    complaint_id = int(data.get("complaint_id"))
                    technician_id = int(data.get("technician_id", 6))
                except (ValueError, TypeError):
                    return self._send_error("Invalid complaint_id or technician_id.", 400)

                reason = data.get("reason", "").strip()
                if len(reason) < 3:
                    return self._send_error("Escalation reason must be specified.", 400)

                cursor.execute("""
                UPDATE complaints
                SET priority = 'critical', escalated = 1, escalation_reason = ?
                WHERE id = ?
                """, (reason, complaint_id))

                # Also record escalation in tickets if associated
                cursor.execute("SELECT id FROM tickets WHERE complaint_id = ?", (complaint_id,))
                ticket_row = cursor.fetchone()
                if ticket_row:
                    cursor.execute("""
                    UPDATE tickets SET status = 'blocked_escalated', priority = 'critical' WHERE id = ?
                    """, (ticket_row["id"],))

                    cursor.execute("""
                    INSERT INTO ticket_events (ticket_id, event_type, from_status, to_status, performed_by_user_id, notes, created_at)
                    VALUES (?, 'escalated', 'in_progress', 'blocked_escalated', ?, ?, ?)
                    """, (ticket_row["id"], technician_id, reason, now_iso))

                cursor.execute("""
                INSERT INTO audit_logs (user_name, action, details, timestamp)
                VALUES (?, ?, ?, ?)
                """, ("Service Team", "ESCALATE_TICKET", f"Escalated Ticket ID {complaint_id} to Ward Supervisor. Reason: {reason}", now_iso))

                conn.commit()
                self._send_json({"success": True, "message": "Ticket successfully escalated to supervisor."})

            # 9. Work Order Status Progression
            elif path == "/api/assignments/update-status":
                try:
                    complaint_id = int(data.get("complaint_id"))
                    technician_id = int(data.get("technician_id", 6))
                except (ValueError, TypeError):
                    return self._send_error("Invalid complaint_id or technician_id.", 400)

                new_status = data.get("status")  # 'on_site', 'in_progress', or 'completed'
                if new_status not in {'on_site', 'in_progress', 'completed'}:
                    return self._send_error("Status must be 'on_site', 'in_progress', or 'completed'.", 400)

                notes = data.get("notes", "")
                proof_photo_url = data.get("proof_photo_url", "")

                cursor.execute("SELECT * FROM service_assignments WHERE complaint_id = ?", (complaint_id,))
                assignment = cursor.fetchone()

                if assignment:
                    if new_status == "completed":
                        cursor.execute("""
                        UPDATE service_assignments 
                        SET status = ?, notes = ?, proof_photo_url = coalesce(?, proof_photo_url), completed_at = ?
                        WHERE complaint_id = ?
                        """, (new_status, notes, proof_photo_url or None, now_iso, complaint_id))
                    else:
                        cursor.execute("""
                        UPDATE service_assignments 
                        SET status = ?, notes = ?
                        WHERE complaint_id = ?
                        """, (new_status, notes, complaint_id))
                else:
                    cursor.execute("""
                    INSERT INTO service_assignments (complaint_id, technician_id, status, notes, proof_photo_url, assigned_at, completed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        complaint_id, technician_id, new_status, notes, proof_photo_url or None,
                        now_iso, now_iso if new_status == "completed" else None
                    ))

                comp_status = "resolved" if new_status == "completed" else "in_progress"

                cursor.execute("""
                UPDATE complaints
                SET status = ?, resolved_at = ?
                WHERE id = ?
                """, (comp_status, now_iso if new_status == "completed" else None, complaint_id))

                # Also update corresponding tickets record if present
                cursor.execute("SELECT id FROM tickets WHERE complaint_id = ?", (complaint_id,))
                tk_row = cursor.fetchone()
                if tk_row:
                    tk_status = "resolved" if new_status == "completed" else ("on_site" if new_status == "on_site" else "in_progress")
                    cursor.execute("""
                    UPDATE tickets SET status = ?, resolution_notes = ?, proof_photo_url = coalesce(?, proof_photo_url), resolved_at = ?
                    WHERE id = ?
                    """, (tk_status, notes, proof_photo_url or None, now_iso if new_status == "completed" else None, tk_row["id"]))

                    cursor.execute("""
                    INSERT INTO ticket_events (ticket_id, event_type, to_status, performed_by_user_id, notes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """, (tk_row["id"], "resolved" if new_status == "completed" else "status_changed", tk_status, technician_id, notes, now_iso))

                # If this complaint was in a cluster and completed, resolve the cluster and linked tickets
                cursor.execute("SELECT cluster_id, ticket_number FROM complaints WHERE id = ?", (complaint_id,))
                comp_row = cursor.fetchone()
                if comp_row and comp_row["cluster_id"] and new_status == "completed":
                    cursor.execute("""
                    UPDATE complaints
                    SET status = 'resolved', resolved_at = ?
                    WHERE cluster_id = ?
                    """, (now_iso, comp_row["cluster_id"]))

                    cursor.execute("""
                    UPDATE issue_clusters
                    SET status = 'resolved', updated_at = ?
                    WHERE id = ?
                    """, (now_iso, comp_row["cluster_id"]))

                    cursor.execute("""
                    INSERT INTO audit_logs (user_name, action, details, timestamp)
                    VALUES (?, ?, ?, ?)
                    """, ("Technician Field Team", "RESOLVE_CLUSTER", f"Master Incident Cluster {comp_row['cluster_id']} marked resolved via repair on {comp_row['ticket_number']}.", now_iso))

                cursor.execute("""
                INSERT INTO audit_logs (user_name, action, details, timestamp)
                VALUES (?, ?, ?, ?)
                """, ("Technician Field Team", "UPDATE_WORK_ORDER", f"Status updated to '{new_status}' on Ticket ID {complaint_id}.", now_iso))

                conn.commit()
                self._send_json({"success": True, "status": comp_status})

            # 10. Citizen Feedback & Rating
            elif path == "/api/feedback":
                try:
                    complaint_id = int(data.get("complaint_id"))
                    rating = int(data.get("rating", 5))
                except (ValueError, TypeError):
                    return self._send_error("Invalid complaint_id or rating.", 400)

                comment = data.get("comment", "")
                cursor.execute("""
                INSERT OR REPLACE INTO feedback (complaint_id, rating, comment, created_at)
                VALUES (?, ?, ?, ?)
                """, (complaint_id, rating, comment, now_iso))

                cursor.execute("""
                INSERT INTO audit_logs (user_name, action, details, timestamp)
                VALUES (?, ?, ?, ?)
                """, ("Citizen Resident", "SUBMIT_FEEDBACK", f"Rated Ticket ID {complaint_id} with {rating} stars.", now_iso))

                conn.commit()
                self._send_json({"success": True})

            # 11. Admin Dispatch & Assignment
            elif path == "/api/assignments/assign":
                try:
                    complaint_id = int(data.get("complaint_id"))
                    technician_id = int(data.get("technician_id"))
                except (ValueError, TypeError):
                    return self._send_error("Invalid complaint_id or technician_id.", 400)

                cursor.execute("""
                INSERT OR REPLACE INTO service_assignments (complaint_id, technician_id, status, notes, assigned_at)
                VALUES (?, ?, 'dispatched', 'Dispatched by Central Operations', ?)
                """, (complaint_id, technician_id, now_iso))

                cursor.execute("UPDATE complaints SET status = 'assigned' WHERE id = ?", (complaint_id,))

                # Synchronize with tickets and ticket_events
                cursor.execute("SELECT id, locality_id, priority FROM complaints WHERE id = ?", (complaint_id,))
                comp_info = cursor.fetchone()
                if comp_info:
                    cursor.execute("SELECT id FROM tickets WHERE complaint_id = ?", (complaint_id,))
                    existing_tk = cursor.fetchone()
                    if existing_tk:
                        cursor.execute("""
                        UPDATE tickets
                        SET assigned_technician_id = ?, status = 'dispatched', dispatched_at = coalesce(dispatched_at, ?)
                        WHERE id = ?
                        """, (technician_id, now_iso, existing_tk["id"]))
                        target_ticket_id = existing_tk["id"]
                    else:
                        wo_num = generate_unique_ticket_number("WO")
                        cursor.execute("""
                        INSERT INTO tickets (ticket_number, complaint_id, locality_id, assigned_technician_id, status, priority, created_at, dispatched_at)
                        VALUES (?, ?, ?, ?, 'dispatched', ?, ?, ?)
                        """, (wo_num, complaint_id, comp_info["locality_id"], technician_id, comp_info["priority"], now_iso, now_iso))
                        target_ticket_id = cursor.lastrowid

                    cursor.execute("""
                    INSERT INTO ticket_events (ticket_id, event_type, from_status, to_status, performed_by_user_id, notes, created_at)
                    VALUES (?, 'assigned', 'pending', 'dispatched', ?, 'Assigned to field technician by Central Operations.', ?)
                    """, (target_ticket_id, technician_id, now_iso))

                cursor.execute("SELECT name FROM users WHERE id = ?", (technician_id,))
                tech_row = cursor.fetchone()
                tech_name = tech_row["name"] if tech_row else f"Technician #{technician_id}"

                cursor.execute("""
                INSERT INTO audit_logs (user_name, action, details, timestamp)
                VALUES (?, ?, ?, ?)
                """, ("Admin Dispatcher", "ASSIGN_TECHNICIAN", f"Assigned {tech_name} to Ticket ID {complaint_id}.", now_iso))

                conn.commit()
                self._send_json({"success": True, "technician_name": tech_name})

            else:
                self._send_error("Unknown action", status=404)

        except ValueError as ve:
            self._send_error(str(ve), status=400)
        except Exception as e:
            print(f"[ERROR] API POST {path}: {type(e).__name__}: {e}")
            self._send_error("Internal server error processing mutation.", status=500)
        finally:
            conn.close()

def start_server(port=None, host=None):
    init_db()
    port = port or int(os.environ.get("PORT", 8000))
    host = host or os.environ.get("HOST", "127.0.0.1")
    server_address = (host, port)
    httpd = ThreadingHTTPServer(server_address, NivoraAPIHandler)
    print(f"============================================================")
    print(f" NIVORA — Intelligent Water Supply Complaint Management")
    print(f" Production Server running at: http://{host}:{port}")
    print(f" System Status: Healthy (Version 2.0-STABLE)")
    print(f" Press Ctrl+C to stop the server.")
    print(f"============================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] Gracefully shutting down NIVORA server...")
        httpd.server_close()

if __name__ == "__main__":
    start_server()
