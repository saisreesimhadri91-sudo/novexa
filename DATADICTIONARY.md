NIVORA Synthetic Demonstration Dataset — Data Dictionary

Dataset Version: 2.0-SYNTHETIC
Random Seed: 42 (Deterministic & Fully Reproducible)
Total Complaints: 10,000
Timespan: 180 Days (2026-04-28 to 2026-10-24 UTC)
Classification: 100% Synthetic Fictional Civic Utility Data (No Real Resident PII)

1. Operational Database Tables
1.1 localities

Fictional municipal administrative wards and water distribution sectors.

Column	Type	Nullable	Description & Constraints	Example
id	INTEGER	No	Primary Key, Auto-increment	1
name	TEXT	No	Descriptive ward name with infrastructure character	North Ward - Sector 4 (Old Town)
zone_code	TEXT	No	Unique alphanumeric sector code	NW-04
center_lat	REAL	No	Locality centroid latitude (
−
90
∘
−90
∘
 to 
90
∘
90
∘
)	28.6280
center_lng	REAL	No	Locality centroid longitude (
−
180
∘
−180
∘
 to 
180
∘
180
∘
)	77.2080
pipeline_grid	TEXT	No	Underlying trunk line distribution specification	Grid Alpha-North (Main 400mm Cast-Iron)
supervisor_name	TEXT	No	Fictional municipal executive officer	Rajendra Prasad
1.2 categories

Standard civic water problem classifications with predefined SLAs.

Column	Type	Nullable	Description & Constraints	Example
id	INTEGER	No	Primary Key	1
name	TEXT	No	Issue classification name	Pipeline Leak / Burst
default_severity	TEXT	No	Baseline severity (low, medium, high, critical)	critical
sla_hours	INTEGER	No	Maximum resolution turnaround target in hours	6
icon	TEXT	No	UI icon identifier	droplets
1.3 users

Fictional residents, field service technicians, and municipal dispatchers.

Column	Type	Nullable	Description & Constraints	Example
id	INTEGER	No	Primary Key, Auto-increment	42
name	TEXT	No	Fictional citizen or staff full name	Aarav Sharma
phone	TEXT	No	Synthetic phone number with fictional prefixes	+91 9845123980
email	TEXT	Yes	Reserved test domain (@example.com, @civic.local)	aarav.sharma42@example.com
role	TEXT	No	User role (resident, technician, admin)	resident
locality_id	INTEGER	Yes	Foreign Key referencing localities(id)	1
privacy_opt_in	INTEGER	No	Flag indicating citizen requests phone/house masking	1
created_at	TEXT	No	ISO 8601 UTC timestamp	2026-04-27T20:00:00Z
1.4 teams

Specialized municipal repair crews and emergency response units.

Column	Type	Nullable	Description & Constraints	Example
id	INTEGER	No	Primary Key, Auto-increment	1
name	TEXT	No	Unique division title	North Rapid Emergency Pipe Squad
specialization	TEXT	No	Operational capability	Heavy Trunk Excavation & Pipeline Burst
locality_id	INTEGER	No	Foreign Key referencing localities(id)	1
lead_technician_id	INTEGER	Yes	Foreign Key referencing users(id)	6
is_active	INTEGER	No	Active deployment status (1=Active, 0=Standby)	1
created_at	TEXT	No	ISO 8601 UTC timestamp	2026-04-27T20:00:00Z
1.5 incidents

Master civic infrastructure failures (clusters of neighbor complaints around a root-cause breakdown).

Column	Type	Nullable	Description & Constraints	Example
id	INTEGER	No	Primary Key, Auto-increment	81
incident_number	TEXT	No	Unique human-readable code	INC-NW-20260714-081
locality_id	INTEGER	No	Foreign Key referencing localities(id)	1
category_id	INTEGER	No	Foreign Key referencing categories(id)	1
title	TEXT	No	Failure summary	Main 400mm Feeder Fissure
description	TEXT	No	Technical incident summary	Road flooding along Metro Circle corridor
severity	TEXT	No	Severity level (low, medium, high, critical)	critical
status	TEXT	No	State (detected, investigating, in_progress, resolved, closed)	resolved
center_lat	REAL	No	Cluster epicenter latitude	28.628412
center_lng	REAL	No	Cluster epicenter longitude	77.208534
radius_meters	REAL	No	Geospatial clustering threshold	250.0
first_observed_at	TEXT	Yes	When failure first began	2026-07-14T09:15:00Z
created_at	TEXT	No	When master ticket was generated	2026-07-14T10:30:00Z
resolved_at	TEXT	Yes	Completion timestamp	2026-07-14T16:45:00Z
1.6 complaints

Individual citizen problem reports (10,000 total records).

Column	Type	Nullable	Description & Constraints	Example
id	INTEGER	No	Primary Key, Auto-increment	1001
ticket_number	TEXT	No	Unique citizen reference code	CMP-2026-01001
resident_id	INTEGER	Yes	Foreign Key referencing users(id)	284
locality_id	INTEGER	No	Foreign Key referencing localities(id)	1
category_id	INTEGER	No	Foreign Key referencing categories(id)	1
description	TEXT	No	Citizen observations	Pressure vanished; water gushing near avenue
incident_time	TEXT	Yes	When citizen first observed the issue (Separated)	2026-07-14 09:30
lat	REAL	No	Latitude coordinate	28.628210
lng	REAL	No	Longitude coordinate	77.208340
address_landmark	TEXT	No	Street landmark visible to technicians	Opposite Metro Gate 2
house_number	TEXT	Yes	Specific flat number (masked for field workers)	Flat 402, Block B
status	TEXT	No	Status (submitted, clustered, assigned, in_progress, resolved, closed)	closed
priority	TEXT	No	Priority level (low, medium, high, critical)	critical
escalated	INTEGER	No	Flag indicating supervisor escalation (1=Escalated, 0=Normal)	0
escalation_reason	TEXT	Yes	Justification for overdue SLA or permit blockage	Road permit required
cluster_id	INTEGER	Yes	Compatibility link to issue_clusters	NULL
created_at	TEXT	No	When complaint was submitted to system	2026-07-14T10:45:00Z
resolved_at	TEXT	Yes	Timestamp when resolution was logged	2026-07-14T16:45:00Z
1.7 incident_complaints

Junction table linking multiple complaints to one master incident while preserving original complaint data intact.

Column	Type	Nullable	Description & Constraints	Example
id	INTEGER	No	Primary Key, Auto-increment	542
incident_id	INTEGER	No	Foreign Key referencing incidents(id)	81
complaint_id	INTEGER	No	Foreign Key referencing complaints(id)	1001
association_type	TEXT	No	Merge mechanism (auto_geo_cluster, manual_admin_merge, resident_1tap_link)	auto_geo_cluster
distance_from_center_meters	REAL	Yes	Distance from master incident epicenter in meters	42.5
associated_at	TEXT	No	Timestamp of association	2026-07-14T10:50:00Z
1.8 tickets & ticket_events

Work orders and lifecycle audit logging.

Column	Type	Nullable	Description & Constraints	Example
ticket_number	TEXT	No	Unique work order reference	WO-INC-2026-00081
incident_id	INTEGER	Yes	Foreign Key referencing incidents(id)	81
assigned_team_id	INTEGER	Yes	Foreign Key referencing teams(id)	1
status	TEXT	No	Status (dispatched, on_site, in_progress, resolved)	resolved
event_type	TEXT	No	In ticket_events: (created, assigned, status_changed, escalated, resolved)	status_changed
2. Ground-Truth Evaluation Datasets

Stored separately under data/ground_truth/ to prevent data leakage during algorithm evaluation.

2.1 ground_truth_complaints.csv
complaint_id: Reference matching complaints.id.
ticket_number: Reference code.
is_clustered: Boolean flag indicating if this report is genuinely part of a multi-household incident.
ground_truth_incident_id: True root-cause incident ID (or NULL for standalone reports).
distance_to_epicenter_meters: Ground truth spatial distance to the failure point.
is_recurrent_incident: Boolean indicating if this report stems from a chronic recurrent pipe failure.
2.2 evaluation_splits.json
Development Set (70% — 7,000 complaints): For tuning clustering distance (
𝑟
∈
[
150
m
,
350
m
]
r∈[150m,350m]) and time window thresholds (
Δ
𝑡
∈
[
12
h
,
72
h
]
Δt∈[12h,72h]).
Held-Out Test Set (30% — 3,000 complaints): Independent test set for computing benchmark Precision, Recall, and F1-score with 0 records overlap.
