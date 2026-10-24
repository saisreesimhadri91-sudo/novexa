import math
import random
from datetime import datetime, timedelta
from .database import get_connection

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great-circle distance between two points 
    on the Earth in meters using the Haversine formula.
    """
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return R * c

def find_nearby_active_issues(lat, lng, radius_meters=300.0):
    """
    Detects any active clusters or pending complaints within the specified radius
    so the user can link with one click instead of re-typing.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Fetch active clusters
    cursor.execute("""
    SELECT c.id, c.cluster_code, c.center_lat, c.center_lng, c.complaint_count, c.status,
           cat.name as category_name, loc.name as locality_name
    FROM issue_clusters c
    JOIN categories cat ON c.category_id = cat.id
    JOIN localities loc ON c.locality_id = loc.id
    WHERE c.status IN ('active', 'investigating')
    """)
    clusters = cursor.fetchall()
    
    nearby_clusters = []
    for cl in clusters:
        dist = haversine_distance(lat, lng, cl["center_lat"], cl["center_lng"])
        if dist <= radius_meters:
            nearby_clusters.append({
                "type": "cluster",
                "id": cl["id"],
                "cluster_code": cl["cluster_code"],
                "category_name": cl["category_name"],
                "locality_name": cl["locality_name"],
                "complaint_count": cl["complaint_count"],
                "distance_meters": round(dist, 1)
            })

    conn.close()
    return nearby_clusters

def evaluate_and_cluster_complaint(complaint_id, lat, lng, category_id, locality_id):
    """
    Evaluates a new complaint against spatial and temporal proximity:
    1. Checks if it falls into an existing open cluster within 250m.
    2. If not, checks if 2 or more recent complaints of the same category exist within 250m.
       If so, forms a new Master Incident Cluster.
    """
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now()
    two_days_ago = (now - timedelta(hours=48)).isoformat()

    # Step 1: Look for existing active cluster within 250 meters of matching category
    cursor.execute("""
    SELECT id, cluster_code, center_lat, center_lng, complaint_count
    FROM issue_clusters
    WHERE category_id = ? AND status IN ('active', 'investigating')
    """, (category_id,))
    active_clusters = cursor.fetchall()

    for cl in active_clusters:
        dist = haversine_distance(lat, lng, cl["center_lat"], cl["center_lng"])
        if dist <= 250.0:
            # Match found! Attach to existing cluster
            new_count = cl["complaint_count"] + 1
            cursor.execute("""
            UPDATE issue_clusters
            SET complaint_count = ?, updated_at = ?
            WHERE id = ?
            """, (new_count, now.isoformat(), cl["id"]))

            cursor.execute("""
            UPDATE complaints
            SET cluster_id = ?, status = 'clustered'
            WHERE id = ?
            """, (cl["id"], complaint_id))

            cursor.execute("""
            INSERT INTO audit_logs (user_name, action, details, timestamp)
            VALUES (?, ?, ?, ?)
            """, ("Repeated-Issue Engine", "LINK_TO_CLUSTER", 
                  f"Linked Complaint ID {complaint_id} to existing Cluster {cl['cluster_code']} ({round(dist, 1)}m away).", 
                  now.isoformat()))

            conn.commit()
            conn.close()
            return {
                "clustered": True,
                "is_new_cluster": False,
                "cluster_code": cl["cluster_code"],
                "cluster_id": cl["id"],
                "distance_meters": round(dist, 1),
                "total_complaints_in_cluster": new_count
            }

    # Step 2: No active cluster yet. Check unclustered open complaints within 250m in last 48 hours
    cursor.execute("""
    SELECT id, ticket_number, lat, lng
    FROM complaints
    WHERE category_id = ? 
      AND id != ? 
      AND cluster_id IS NULL
      AND status IN ('submitted', 'verified', 'assigned', 'in_progress')
      AND created_at >= ?
    """, (category_id, complaint_id, two_days_ago))
    candidates = cursor.fetchall()

    matching_ids = []
    for cand in candidates:
        dist = haversine_distance(lat, lng, cand["lat"], cand["lng"])
        if dist <= 250.0:
            matching_ids.append((cand["id"], dist))

    # If we have at least 2 existing candidates + the current complaint = 3 complaints
    if len(matching_ids) >= 2:
        # Create a new Master Cluster
        cursor.execute("SELECT zone_code FROM localities WHERE id = ?", (locality_id,))
        zone_row = cursor.fetchone()
        zone_code = zone_row["zone_code"] if zone_row else "GEN"

        cluster_code = f"CLS-{zone_code}-{now.strftime('%Y%m%d%H%M%S')}-{random.randint(10, 99)}"
        total_in_cluster = len(matching_ids) + 1

        cursor.execute("""
        INSERT INTO issue_clusters (cluster_code, locality_id, category_id, center_lat, center_lng, radius_meters, complaint_count, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, 250.0, ?, 'active', ?, ?)
        """, (cluster_code, locality_id, category_id, lat, lng, total_in_cluster, now.isoformat(), now.isoformat()))
        new_cluster_id = cursor.lastrowid

        # Attach the current complaint
        cursor.execute("""
        UPDATE complaints SET cluster_id = ?, status = 'clustered' WHERE id = ?
        """, (new_cluster_id, complaint_id))

        # Attach the neighboring candidates
        for cid, _ in matching_ids:
            cursor.execute("""
            UPDATE complaints SET cluster_id = ?, status = 'clustered' WHERE id = ?
            """, (new_cluster_id, cid))

        cursor.execute("""
        INSERT INTO audit_logs (user_name, action, details, timestamp)
        VALUES (?, ?, ?, ?)
        """, ("Repeated-Issue Engine", "CREATE_CLUSTER", 
              f"Auto-grouped {total_in_cluster} complaints into Master Cluster {cluster_code} within 250m.", 
              now.isoformat()))

        conn.commit()
        conn.close()
        return {
            "clustered": True,
            "is_new_cluster": True,
            "cluster_code": cluster_code,
            "cluster_id": new_cluster_id,
            "total_complaints_in_cluster": total_in_cluster
        }

    conn.commit()
    conn.close()
    return {"clustered": False}
