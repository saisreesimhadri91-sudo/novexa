-- ====================================================================
-- NIVORA Relational Synthetic Seed Data
-- File: supabase/seed.sql
-- Covers all 9 Core Entities:
-- localities, categories, profiles, teams, incidents, complaints,
-- incident_complaints, tickets, ticket_events, and audit_logs.
-- Timezone: UTC (ISO 8601)
-- ====================================================================

-- 1. Localities (Representative Wards)
INSERT INTO public.localities (id, name, zone_code, center_lat, center_lng, pipeline_grid, supervisor_name)
VALUES
    ('11111111-1111-1111-1111-111111111111', 'North Ward - Sector 4', 'NW-04', 28.6280, 77.2080, 'Grid Alpha-North (Main 400mm)', 'Rajendra Prasad'),
    ('22222222-2222-2222-2222-222222222222', 'East Ward - Lakeview', 'EW-02', 28.6335, 77.2250, 'Grid Beta-East (Lake Line)', 'Sunita Rao'),
    ('33333333-3333-3333-3333-333333333333', 'South Ward - Green Valley', 'SW-09', 28.6140, 77.2120, 'Grid Gamma-South (Highlands)', 'Col. Arvind Mehta'),
    ('44444444-4444-4444-4444-444444444444', 'West Ward - Industrial Belt', 'WW-05', 28.6210, 77.1950, 'Grid Delta-West (Industrial Feeder)', 'Vikram Solanki')
ON CONFLICT (id) DO NOTHING;

-- 2. Categories
INSERT INTO public.categories (id, name, default_severity, sla_hours, icon)
VALUES
    ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'Pipeline Leak / Burst', 'critical', 6, 'droplets'),
    ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'Water Contamination', 'critical', 8, 'alert-triangle'),
    ('cccccccc-cccc-cccc-cccc-cccccccccccc', 'No Water Supply', 'high', 12, 'slash'),
    ('dddddddd-dddd-dddd-dddd-dddddddddddd', 'Low Water Pressure', 'medium', 24, 'gauge'),
    ('eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee', 'Faulty Valve / Meter', 'low', 48, 'wrench')
ON CONFLICT (id) DO NOTHING;

-- 3. Users in auth.users (Supabase local test identities)
INSERT INTO auth.users (id, instance_id, aud, role, email, encrypted_password, email_confirmed_at, raw_app_meta_data, raw_user_meta_data, created_at, updated_at)
VALUES
    ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'resident.a@nivora.io', crypt('password123', gen_salt('bf')), now(), '{"provider":"email","providers":["email"]}', '{"full_name":"Priya Sharma","role":"resident"}', now(), now()),
    ('00000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'resident.b@nivora.io', crypt('password123', gen_salt('bf')), now(), '{"provider":"email","providers":["email"]}', '{"full_name":"Rahul Verma","role":"resident"}', now(), now()),
    ('00000000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'technician.rajesh@nivora.gov', crypt('password123', gen_salt('bf')), now(), '{"provider":"email","providers":["email"]}', '{"full_name":"Rajesh Kumar","role":"service_team"}', now(), now()),
    ('00000000-0000-0000-0000-000000000004', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'admin@nivora.gov', crypt('password123', gen_salt('bf')), now(), '{"provider":"email","providers":["email"]}', '{"full_name":"City Water Commissioner","role":"admin"}', now(), now())
ON CONFLICT (id) DO NOTHING;

-- 4. Profiles
INSERT INTO public.profiles (id, full_name, phone_number, role, locality_id, privacy_opt_in)
VALUES
    ('00000000-0000-0000-0000-000000000001', 'Priya Sharma', '+91 9876543210', 'resident', '11111111-1111-1111-1111-111111111111', true),
    ('00000000-0000-0000-0000-000000000002', 'Rahul Verma', '+91 9811223344', 'resident', '11111111-1111-1111-1111-111111111111', true),
    ('00000000-0000-0000-0000-000000000003', 'Rajesh Kumar', '+91 9700112233', 'service_team', '11111111-1111-1111-1111-111111111111', false),
    ('00000000-0000-0000-0000-000000000004', 'City Water Commissioner', '+91 9999900000', 'admin', NULL, false)
ON CONFLICT (id) DO UPDATE SET role = EXCLUDED.role, locality_id = EXCLUDED.locality_id;

-- 5. Teams (Field Crews)
INSERT INTO public.teams (id, name, specialization, locality_id, lead_technician_id, is_active)
VALUES
    ('77777777-7777-7777-7777-777777777771', 'North Ward Rapid Repair Crew', 'Heavy Pipe Burst & Excavation', '11111111-1111-1111-1111-111111111111', '00000000-0000-0000-0000-000000000003', true),
    ('77777777-7777-7777-7777-777777777772', 'East Ward Water Quality Division', 'Contamination & Chemical Remediation', '22222222-2222-2222-2222-222222222222', NULL, true),
    ('77777777-7777-7777-7777-777777777773', 'South Ward Pressure Management Unit', 'Booster Valves & Regulators', '33333333-3333-3333-3333-333333333333', NULL, true)
ON CONFLICT (id) DO NOTHING;

-- 6. Master Incidents
INSERT INTO public.incidents (
    id, incident_number, locality_id, category_id, title, description,
    severity, status, center_lat, center_lng, radius_meters, first_observed_at, created_at
) VALUES (
    '99999999-9999-9999-9999-999999999999',
    'INC-NW-2026-081',
    '11111111-1111-1111-1111-111111111111',
    'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
    'Main 400mm Feeder Line Rupture (Sector 4 Avenue)',
    'Multiple reports of road flooding and water loss along Metro Gate 2 avenue.',
    'critical',
    'in_progress',
    28.6282, 77.2084,
    250.0,
    now() - interval '4 hours',
    now() - interval '3 hours 45 minutes'
) ON CONFLICT (id) DO NOTHING;

-- 7. Complaints (Separates occurred_at and created_at)
INSERT INTO public.complaints (
    id, ticket_number, locality_id, category_id, resident_id, is_anonymous,
    anonymous_tracking_hash, description, occurred_at, created_at, latitude, longitude,
    address_landmark, house_number, status, priority
) VALUES
    -- Complaint 1: Resident A
    (
        'c1111111-1111-1111-1111-111111111111',
        'CMP-2026-1001',
        '11111111-1111-1111-1111-111111111111',
        'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
        '00000000-0000-0000-0000-000000000001',
        false,
        NULL,
        'Severe gushing water near main avenue circle; pressure has vanished.',
        now() - interval '4 hours',               -- occurred_at
        now() - interval '3 hours 45 minutes',   -- created_at
        28.6282, 77.2083,
        'Opposite Metro Gate 2',
        'Flat 402, Block B',
        'associated',
        'critical'
    ),
    -- Complaint 2: Resident B
    (
        'c2222222-2222-2222-2222-222222222222',
        'CMP-2026-1002',
        '11111111-1111-1111-1111-111111111111',
        'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
        '00000000-0000-0000-0000-000000000002',
        false,
        NULL,
        'Major water fountain in front of Community Hall. Road is flooded.',
        now() - interval '3 hours',               -- occurred_at
        now() - interval '2 hours 30 minutes',   -- created_at
        28.6284, 77.2086,
        'Near Community Center',
        'House 12, Lane 3',
        'associated',
        'critical'
    ),
    -- Complaint 3: Anonymous Report with Cryptographic Tracking Token
    (
        'c3333333-3333-3333-3333-333333333333',
        'CMP-2026-ANON01',
        '22222222-2222-2222-2222-222222222222',
        'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
        NULL,
        true,
        encode(digest('demo_secret_token_12345', 'sha256'), 'hex'),
        'Strong chlorine and chemical smell detected in public fountain tap.',
        now() - interval '1 hour 30 minutes',
        now() - interval '1 hour',
        28.6338, 77.2255,
        'Lakeview Promenade Public Garden',
        NULL,
        'submitted',
        'high'
    )
ON CONFLICT (id) DO NOTHING;

-- 8. Incident-Complaints Junction (Many Complaints to One Incident)
INSERT INTO public.incident_complaints (id, incident_id, complaint_id, association_type, distance_from_center_meters, associated_at)
VALUES
    ('88888888-8888-8888-8888-888888888881', '99999999-9999-9999-9999-999999999999', 'c1111111-1111-1111-1111-111111111111', 'auto_geo_cluster', 35.0, now() - interval '2 hours'),
    ('88888888-8888-8888-8888-888888888882', '99999999-9999-9999-9999-999999999999', 'c2222222-2222-2222-2222-222222222222', 'auto_geo_cluster', 55.0, now() - interval '2 hours')
ON CONFLICT (id) DO NOTHING;

-- 9. Tickets (Master Work Order Dispatched to Field Crew)
INSERT INTO public.tickets (
    id, ticket_number, incident_id, complaint_id, locality_id,
    assigned_team_id, assigned_technician_id, status, priority,
    sla_deadline, resolution_notes, proof_photo_url, created_at, dispatched_at
) VALUES (
    '55555555-5555-5555-5555-555555555555',
    'WO-2026-0042',
    '99999999-9999-9999-9999-999999999999',
    NULL,
    '11111111-1111-1111-1111-111111111111',
    '77777777-7777-7777-7777-777777777771',
    '00000000-0000-0000-0000-000000000003',
    'in_progress',
    'critical',
    now() + interval '3 hours',
    'Isolated main junction valve; replacing ruptured collar clamp.',
    'https://images.unsplash.com/photo-1584622650111-993a426fbf0a?auto=format&fit=crop&w=400&q=80',
    now() - interval '2 hours',
    now() - interval '1 hour 45 minutes'
) ON CONFLICT (id) DO NOTHING;

-- 10. Ticket Events (Lifecycle Audit: Creation, Assignment & Status Changes)
INSERT INTO public.ticket_events (ticket_id, event_type, from_status, to_status, from_team_id, to_team_id, performed_by_user_id, notes, created_at)
VALUES
    ('55555555-5555-5555-5555-555555555555', 'created', NULL, 'dispatched', NULL, '77777777-7777-7777-7777-777777777771', '00000000-0000-0000-0000-000000000004', 'Work order initialized from Master Incident INC-NW-2026-081.', now() - interval '2 hours'),
    ('55555555-5555-5555-5555-555555555555', 'assigned', 'dispatched', 'dispatched', NULL, '77777777-7777-7777-7777-777777777771', '00000000-0000-0000-0000-000000000004', 'Assigned to North Ward Rapid Repair Crew.', now() - interval '1 hour 45 minutes'),
    ('55555555-5555-5555-5555-555555555555', 'status_changed', 'dispatched', 'on_site', '77777777-7777-7777-7777-777777777771', '77777777-7777-7777-7777-777777777771', '00000000-0000-0000-0000-000000000003', 'Crew arrived at Metro Gate 2 avenue with 400mm replacement kit.', now() - interval '1 hour'),
    ('55555555-5555-5555-5555-555555555555', 'status_changed', 'on_site', 'in_progress', '77777777-7777-7777-7777-777777777771', '77777777-7777-7777-7777-777777777771', '00000000-0000-0000-0000-000000000003', 'Isolated 400mm feeder line; beginning excavation.', now() - interval '30 minutes')
ON CONFLICT DO NOTHING;

-- 11. Audit Logs
INSERT INTO public.audit_logs (user_id, user_name, action, target_entity, target_id, details, timestamp)
VALUES
    ('00000000-0000-0000-0000-000000000004', 'City Water Commissioner', 'CREATE_INCIDENT', 'incidents', '99999999-9999-9999-9999-999999999999', 'Grouped 2 complaints into Master Incident INC-NW-2026-081 within 250m.', now() - interval '2 hours'),
    ('00000000-0000-0000-0000-000000000004', 'City Water Commissioner', 'DISPATCH_TICKET', 'tickets', '55555555-5555-5555-5555-555555555555', 'Dispatched North Ward Rapid Repair Crew.', now() - interval '1 hour 45 minutes')
ON CONFLICT DO NOTHING;
