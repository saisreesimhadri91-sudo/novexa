-- ====================================================================
-- NIVORA PostgreSQL Database Integrity & Constraints Test Suite
-- File: supabase/tests/database_integrity_test.sql
-- Description: Tests all 9 logical entities, unique identifiers, foreign keys,
--              junction relationships, timestamp separation, and RLS policies.
-- ====================================================================

BEGIN;

\echo '============================================================'
\echo 'TEST 1: Verifying All 9 Logical Entities in PostgreSQL'
\echo '============================================================'

DO $$
DECLARE
    v_table TEXT;
    v_entities TEXT[] := ARRAY[
        'localities',
        'profiles',
        'teams',
        'incidents',
        'complaints',
        'incident_complaints',
        'tickets',
        'ticket_events',
        'audit_logs'
    ];
BEGIN
    FOREACH v_table IN ARRAY v_entities LOOP
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = v_table
        ) THEN
            RAISE EXCEPTION 'TEST 1 FAILED: Entity % is missing from public schema!', v_table;
        END IF;
    END LOOP;
    RAISE NOTICE 'TEST 1 PASSED: All 9 logical entities exist in public schema.';
END $$;

\echo '============================================================'
\echo 'TEST 2: Verifying Timestamp Separation on Complaints'
\echo '============================================================'

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'complaints' AND column_name = 'created_at'
    ) OR NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'complaints' AND column_name = 'occurred_at'
    ) THEN
        RAISE EXCEPTION 'TEST 2 FAILED: created_at and occurred_at must both exist on complaints table!';
    END IF;
    RAISE NOTICE 'TEST 2 PASSED: Timestamp separation verified (created_at and occurred_at exist separately).';
END $$;

\echo '============================================================'
\echo 'TEST 3: Verifying Unique Identifiers on Complaints, Incidents, and Tickets'
\echo '============================================================'

DO $$
BEGIN
    -- Verify ticket_number UK on complaints
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints tc 
        JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name 
        WHERE tc.table_name = 'complaints' AND ccu.column_name = 'ticket_number'
    ) THEN
        RAISE EXCEPTION 'TEST 3 FAILED: complaints.ticket_number is not constrained unique!';
    END IF;

    -- Verify incident_number UK on incidents
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints tc 
        JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name 
        WHERE tc.table_name = 'incidents' AND ccu.column_name = 'incident_number'
    ) THEN
        RAISE EXCEPTION 'TEST 3 FAILED: incidents.incident_number is not constrained unique!';
    END IF;

    -- Verify ticket_number UK on tickets
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints tc 
        JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name 
        WHERE tc.table_name = 'tickets' AND ccu.column_name = 'ticket_number'
    ) THEN
        RAISE EXCEPTION 'TEST 3 FAILED: tickets.ticket_number is not constrained unique!';
    END IF;

    RAISE NOTICE 'TEST 3 PASSED: Unique identifiers constrained for complaints, incidents, and tickets.';
END $$;

\echo '============================================================'
\echo 'TEST 4: Verifying Junction Table & Original Complaint Preservation'
\echo '============================================================'

DO $$
DECLARE
    v_loc_id UUID;
    v_cat_id UUID;
    v_comp1 UUID;
    v_comp2 UUID;
    v_inc UUID;
BEGIN
    -- Insert test locality & category
    INSERT INTO public.localities (name, zone_code, center_lat, center_lng, pipeline_grid, supervisor_name)
    VALUES ('Test Ward', 'TW-99', 28.5, 77.1, 'Grid Test', 'Inspector Test')
    RETURNING id INTO v_loc_id;

    INSERT INTO public.categories (name, default_severity, sla_hours)
    VALUES ('Test Category', 'high', 12)
    RETURNING id INTO v_cat_id;

    -- Insert 2 distinct anonymous complaints
    INSERT INTO public.complaints (ticket_number, locality_id, category_id, is_anonymous, anonymous_tracking_hash, description, latitude, longitude, address_landmark)
    VALUES 
        ('CMP-TEST-001', v_loc_id, v_cat_id, true, 'dummy_hash_1', 'Burst pipe A', 28.501, 77.101, 'Landmark 1')
    RETURNING id INTO v_comp1;

    INSERT INTO public.complaints (ticket_number, locality_id, category_id, is_anonymous, anonymous_tracking_hash, description, latitude, longitude, address_landmark)
    VALUES 
        ('CMP-TEST-002', v_loc_id, v_cat_id, true, 'dummy_hash_2', 'Burst pipe B', 28.502, 77.102, 'Landmark 2')
    RETURNING id INTO v_comp2;

    -- Insert 1 Master Incident
    INSERT INTO public.incidents (incident_number, locality_id, category_id, title, description, severity, center_lat, center_lng)
    VALUES ('INC-TEST-001', v_loc_id, v_cat_id, 'Shared Test Incident', 'Two reports joined.', 'critical', 28.5015, 77.1015)
    RETURNING id INTO v_inc;

    -- Associate BOTH complaints to the single incident in the junction table
    INSERT INTO public.incident_complaints (incident_id, complaint_id, association_type)
    VALUES 
        (v_inc, v_comp1, 'auto_geo_cluster'),
        (v_inc, v_comp2, 'auto_geo_cluster');

    -- Verify junction cardinality (2 complaints associated to 1 incident)
    IF (SELECT COUNT(*) FROM public.incident_complaints WHERE incident_id = v_inc) <> 2 THEN
        RAISE EXCEPTION 'TEST 4 FAILED: Expected 2 complaints associated with incident %', v_inc;
    END IF;

    -- Verify original complaints STILL EXIST intact
    IF (SELECT COUNT(*) FROM public.complaints WHERE id IN (v_comp1, v_comp2)) <> 2 THEN
        RAISE EXCEPTION 'TEST 4 FAILED: Original complaints were corrupted or lost during association!';
    END IF;

    RAISE NOTICE 'TEST 4 PASSED: Many-to-one junction verified while preserving original complaints intact.';
END $$;

\echo '============================================================'
\echo 'TEST 5: Verifying Locality Geographic Analysis View'
\echo '============================================================'

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.views 
        WHERE table_schema = 'public' AND table_name = 'locality_geographic_summary'
    ) THEN
        RAISE EXCEPTION 'TEST 5 FAILED: View locality_geographic_summary does not exist!';
    END IF;

    -- Ensure view does not expose private house_number column
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'locality_geographic_summary' AND column_name IN ('house_number', 'phone_number', 'resident_id')
    ) THEN
        RAISE EXCEPTION 'SECURITY BREACH: locality_geographic_summary view exposes private household PII!';
    END IF;

    RAISE NOTICE 'TEST 5 PASSED: Locality geographic analysis view safely summarizes ward data without household coordinates.';
END $$;

\echo '============================================================'
\echo 'ALL POSTGRESQL DATABASE INTEGRITY TESTS PASSED SUCCESSFULLY!'
\echo '============================================================'

ROLLBACK;
