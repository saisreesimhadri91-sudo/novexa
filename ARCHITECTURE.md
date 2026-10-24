NIVORA Water Management System — Master Architecture & Implementation Plan

System Version: 2.0-STABLE
Classification: Municipal Civic Utility Infrastructure
Author: Senior Full-Stack, Database, QA & Security Engineering Team
Date: October 2026

Executive Summary

The NIVORA Water Management System is a mission-critical, multi-tier civic utility platform engineered to modernize municipal water supply complaint management, geospatial infrastructure failure clustering, field-crew work order dispatching, and executive water health analytics.

This document establishes the Master Architecture, requirements checklist, database entity design, API specification, security controls, and phase-by-phase verification criteria spanning Phase 1 through Phase 8 (with Stage 9 Production Acceptance and Stage 10 Operational Readiness).

1. System Objectives & Intended Users
1.1 Core Objectives
Eliminate Duplicate Dispatches: Automatically cluster nearby neighbor reports within a 
250
m
250m spatial radius and 
48
h
48h temporal window into single Master Incidents, preventing redundant crew dispatches.
Citizen Empowerment & 1-Tap Confirmation: Enable citizens to report water issues in 3 intuitive steps or attach to an existing neighborhood incident with one tap ("I Have This Issue Too").
Privacy by Design: Safeguard citizen telephone numbers and private flat/apartment numbers from field contractor views using automated masking, while retaining precise landmarks and navigation coordinates.
Data-Driven Municipal Intelligence: Provide ward supervisors and administrators with real-time GIS locality maps, ward health scores (
0
–
100
0–100), SLA compliance tracking, MTTR monitoring, and exportable audit records.
Separation of Occurrence and Submission Times: Reliably preserve the exact timestamp when citizens first observed water failures separately from when reports were logged in the database.
1.2 User Personas & Roles
Persona	Role Identifier	Access & Permission Boundaries	Primary Workflows
Resident	resident	Self-Service & Local Ward: Can view own complaints, view nearby cluster alerts, file complaints, link to active neighborhood clusters, and rate closed resolutions. PII is protected.	3-step complaint submission; 1-tap cluster join; complaint tracking; 5-star resolution feedback.
Service Team	technician	Assigned Work Orders: Receives dispatched tickets for assigned wards. Can inspect landmarks, update progress (on_site, in_progress, completed), submit photo proof, and escalate overdue blockers to supervisors. Cannot access resident private phones.	On-site check-in; proof upload; repair notes; supervisor escalation.
Ward Supervisor	supervisor	Ward Operational Authority: Manages ward teams, reviews health scores, resolves escalations, merges/splits incidents, and overrides priorities.	Priority escalation review; crew reassignment; incident lifecycle management.
Municipal Administrator	admin	System-Wide Central Operations: Unrestricted access to all 15 wards, citywide KPI counters, Leaflet GIS proximity map, team dispatching, CSV/PDF reporting, and immutable audit logs.	Real-time operations monitoring; emergency dispatch; policy configuration; data exports.
2. 12 Core Functional Modules
Module Breakdown
Municipal Locality Dashboard: Executive KPI tiles (Total Complaints, Active Recurring Clusters, SLA Compliance Rate, MTTR in hours, Citizen Satisfaction Score).
Geographic Locality and Ward Map: Leaflet.js interactive GIS map displaying color-coded incident markers, 
250
m
250m PostGIS/Haversine clustering radiuses, and ward distribution grids.
Locality Health Score & Explainable Breakdown: Dynamic algorithm scoring wards from 
0
0 to 
100
100 based on complaint volume, active unaddressed leaks, contamination severity, and MTTR compliance.
Water Incident Reporting & Tracking: 3-step submission wizard with category classification, locality selection, GPS auto-fetch, landmark entry, and real-time status timeline.
Incident Priority Management: Automatic baseline assignment (low, medium, high, critical) based on category SLA, escalating dynamically when clusters expand.
Incident Merging and Splitting: Administrative ability to link disparate reports into a single root-cause trunk line failure or decouple falsely grouped complaints.
Supervisor Escalation and Priority Overrides: Mechanism for field technicians to trigger supervisor intervention when work orders face physical or administrative blockages.
Service-Team Field Console: Mobile-first technician interface with masked resident PII, GPS navigation landmarks, one-click status transitions, and photo proof submission.
Work Orders, Technician Assignments & Notes: Relational work order tracking (tickets table) linked to field crews (teams table) with comprehensive event logging (ticket_events).
SLA & Performance Analytics: Calculation of Mean Time to Resolve (MTTR), SLA compliance percentages across 15 wards, and technician performance leaderboards.
CSV & PDF Reporting: Client- and server-side data extraction tools generating filtered operational records and executive PDF summaries.
User Roles, Permissions & Audit History: Role-Based Access Control (RBAC) enforced across API endpoints with tamper-evident audit logging (audit_logs table).
3. Relational Database Architecture & 9 Core Entities

The system models municipal water operations using 9 primary relational entities, supporting PostgreSQL / PostGIS in production (via Supabase) and SQLite with Haversine spatial calculations in local development.

3.1 Entity Specifications
localities: Administrative municipal wards (e.g., North Ward, West Ward). Contains geographic centroids (center_lat, center_lng), pipeline grid designations, and supervisor assignments.
categories: Issue classifications (Pipeline Leak / Burst, Water Contamination, Low Water Pressure, Drainage / Overflow, Billing / Meter Fault) with predefined default severity and SLA deadlines (hours).
users: Resident citizens, field technicians, supervisors, and central administrators. Stores hashed credentials, phone numbers, email addresses, and privacy opt-in preferences.
teams: Specialized field repair crews (e.g., Heavy Pipe Burst Squad, Quality Investigation Unit) assigned to localities and led by senior technicians.
incidents: Master infrastructure failures representing root-cause physical breakdowns. Assigned unique incident_number (UK), epicenter coordinates, and 
250
m
250m proximity threshold.
complaints: Citizen reports (10,000 synthetic records in development). Strictly separates incident_time (when failure was observed) from created_at (when report was submitted).
incident_complaints: Many-to-one junction preserving individual citizen reports, distances to epicenter, and association types (auto_geo_cluster, manual_admin_merge, resident_1tap_link).
tickets: Master work orders dispatched to teams or technicians. Tracks SLA deadlines, investigation notes, resolution timestamps, and proof photo URLs.
ticket_events: Immutable lifecycle audit log recording every work order event (created, assigned, status_changed, escalated, resolved, closed).
audit_logs: System-wide operations log capturing user identity, action type, description, and UTC timestamp.
3.2 Timezone & Timestamp Standard

All database timestamps are stored strictly as ISO 8601 UTC strings (YYYY-MM-DDTHH:MM:SSZ or TIMESTAMPTZ in PostgreSQL). The frontend converts UTC timestamps into the user's localized browser timezone (e.g., IST UTC+05:30).

4. API & Data Flow Architecture

The backend provides a RESTful API layer interfacing between the client-side SPA and the database engine.

4.1 Implemented & Required Endpoint Matrix
Method	Endpoint	Access Role	Description & Data Contract
GET	/api/health	Public	System health check returning server status, uptime, and database connectivity.
GET	/api/meta	Public	Returns reference lists of localities, categories, and active users.
GET	/api/complaints	Authenticated	Returns complaints filtered by role, locality_id, category_id, and status. Enforces privacy masking.
POST	/api/complaints	Resident	Creates a new citizen complaint. Executes spatial clustering evaluation.
POST	/api/complaints/quick-link	Resident	Links a resident directly to an active incident cluster (1-Tap Confirmation).
POST	/api/complaints/confirm-resolution	Resident	Resident confirms repair resolution and records feedback rating (
1
–
5
1–5).
GET	/api/nearby-issues	Public	Returns active incident clusters within specified radius (default 
300
m
300m).
GET	/api/clusters	Admin / Supervisor	Returns active and investigating clusters with grouped complaint details.
POST	/api/incidents/merge	Admin / Supervisor	Manually merges multiple complaints/incidents into a single master incident.
POST	/api/incidents/split	Admin / Supervisor	Decouples an incorrectly associated complaint from an incident.
POST	/api/incidents/override-priority	Supervisor	Overrides incident priority level with mandatory audit justification.
GET	/api/tickets	Technician / Admin	Retrieves work orders assigned to a technician or team.
POST	/api/assignments/assign	Admin / Supervisor	Dispatches a technician or team to a complaint or incident.
POST	/api/assignments/update-status	Technician	Updates work order status (on_site, in_progress, completed) with proof photo.
POST	/api/complaints/escalate	Technician	Escalates blocked or overdue work order to ward supervisor.
GET	/api/analytics/locality	Admin / Supervisor	Returns ward-level health scores, leak counts, and contamination rates.
GET	/api/analytics/performance	Admin	Computes MTTR, total complaints, SLA compliance rate, and technician leaderboard.
GET	/api/reports/export/csv	Admin	Generates filtered operational CSV export.
GET	/api/audit-logs	Admin	Returns tamper-evident system audit trail (latest 100 events).
5. UI/UX Design System — Light Purple & Royal Elegant Theme

The frontend is styled using a modern, luxurious, royal, and elegant SaaS-style interface.

5.1 Palette Tokens
Semantic Token	Hex Code	Purpose & Usage
Primary Royal Purple	#5B21B6	Primary branding, hero headings, active navigation states, primary buttons.
Secondary Purple	#7C3AED	Hover states, secondary action buttons, interactive controls.
Elegant Lavender	#A78BFA	Accent borders, badges, chart secondary series, selected states.
Light Purple	#EDE9FE	Subtle container backgrounds, table header accents, tag backgrounds.
Soft Lavender Background	#F5F3FF	Main application and page backdrop gradient foundation.
Pure White	#FFFFFF	Card surfaces, modal containers, data tables, dropdowns.
Dark Royal Navy	#1E1B4B	Primary body text, high-contrast headings, KPI numbers.
Muted Text	#6B7280	Subtitles, timestamp indicators, metadata captions.
Light Purple Border	#DDD6FE	Subtle borders for cards, inputs, and divider lines.
5.2 Typography Standards
Marketing & Prominent Headings: Playfair Display (or elegant serif fallback) for hero banners and major landing page typography.
Dashboard & Functional UI: Inter / Plus Jakarta Sans for clean, legible data tables, forms, and charts.
5.3 Preserved Usability Colors

While the UI shell and brand identity use the Royal Purple theme, semantic warning and severity colors are preserved for accessibility:

🔴 Red (#EF4444): High / Critical Severity, Pipeline Burst, Urgent Alarms.
🟠 Amber (#F59E0B): Water Contamination, Escalated Items, Warnings.
🔵 Blue / Sky (#0EA5E9): Low Pressure, Dispatched Orders.
🟢 Green / Emerald (#10B981): Resolved / Closed Incidents, High Health Score.
6. Security, Privacy & Availability Plan
Resident PII Masking: Citizen phone numbers (+91 98****3210) and apartment numbers are masked in all field contractor views. Technicians navigate solely via street landmark and GPS coordinates.
Credential & Secret Protection: No service-role keys, database passwords, or privileged administrative tokens are bundled in client-side code or public endpoints.
Database Row-Level Security (RLS): Enforced via Supabase PostgreSQL policies:
Residents can only read their own complaints and view anonymized cluster alerts.
Technicians can only view and update work orders assigned to their team.
Admins and supervisors hold privileged operational rights through verified server-side sessions.
Input Validation & Sanitization: Strict type checking on coordinates (latitude 
∈
[
−
90
,
90
]
∈[−90,90], longitude 
∈
[
−
180
,
180
]
∈[−180,180]), allowed status enum transitions, and HTML character escaping.
Rate Limiting & Request Throttling: API boundaries protect against rapid complaint flooding and automated scraping.
7. Current Implementation State & Gap Analysis (Phases 1–4)
Phase	Defined Objective	Current Repository State	Verification Status	Identified Gap / Required Action
Phase 1	Requirements & Master Architecture	Documented in README.md, DATA_DICTIONARY.md, and compiled into docs/ARCHITECTURE.md.	COMPLETED & VERIFIED	Architecture formalized; ready for review.
Phase 2	Frontend Development & Royal Purple Theme	SPA in static/index.html exists but uses legacy Blue & Teal theme, lacks Landing Page, Auth modal, and 3-step wizard.	INCOMPLETE / NEEDS IMPLEMENTATION	First incomplete phase. Implement Light Purple & Royal Elegant design system across all screens.
Phase 3	Database Architecture & PostGIS	Local SQLite database (nivora.db) operational with 10,000 complaints, 450 incidents, 9 entities; 7/7 tests pass. Supabase migrations prepared.	LOCALLY OPERATIONAL / MIGRATIONS PREPARED	Local SQLite verified. Remote Supabase requires user credentials when connecting to cloud staging.
Phase 4	Backend API Development	server.py implements basic complaint, cluster, analytics, and dispatch routes in Python 3.11.	PARTIALLY IMPLEMENTED	Implement missing endpoints: relational tickets, incident merge/split, supervisor escalation override, health check, PDF export.
8. Phase-by-Phase Acceptance Criteria & Roadmap
Phase Acceptance Criteria
Phase 1 (Architecture): System requirements, user personas, 12 modules, 9 entities, API design, and roadmap documented. 
→
→ READY FOR APPROVAL.
Phase 2 (Frontend): Light Purple and Royal Elegant theme applied consistently; Landing Page, Login/Auth modal, Resident Portal (3-step wizard), Administrator Portal, GIS Map, Service Team Portal, and Reports verified in browser.
Phase 3 (Database): 9 entities verified with unique identifiers, timestamp separation, junction cardinality, foreign keys, and locality aggregation passing 100% of test suites.
Phase 4 (Backend APIs): All 18 endpoints active with structured error handling, payload validation, and server-side RBAC.
Phase 5 (Integration): Real-time UI updates, persistent mutations in database, no mock data fallback in production routes.
Phase 6 (QA & Testing): End-to-end user journeys pass, zero regressions, dataset integrity confirmed.
Phase 7 (Security): Secrets audited, zero exposed tokens, RLS validated, PII masking confirmed.
Phase 8 (Deployment): Production build verified, health check responding, live smoke tests executed.
Stage 9 (Production Acceptance): HTTPS operational, no console errors, evidence recorded.
Stage 10 (Operational Readiness): Escalation procedures, monitoring, backup/restore procedures documented.
