-- ====================================================================
-- AQUAPULSE RLS & Access Control Security Test Suite
-- File: supabase/tests/rls_security_test.sql
-- Description: Verifies tenant privacy boundaries, prevents cross-resident
--              access, tests anonymous token tracking, and confirms staff access.
-- ====================================================================

BEGIN;

-- Helper to set simulated authentication context in PostgreSQL
CREATE OR REPLACE PROCEDURE test_as_user(p_uid UUID, p_role TEXT) AS $$
BEGIN
    PERFORM set_config('request.jwt.claim.sub', COALESCE(p_uid::text, ''), true);
    PERFORM set_config('request.jwt.claim.role', p_role, true);
    PERFORM set_config('role', p_role, true);
END;
$$ LANGUAGE plpgsql;

\echo '============================================================'
\echo 'TEST 1: Resident A (Priya Sharma) Tenant Privacy'
\echo '============================================================'
CALL test_as_user('00000000-0000-0000-0000-000000000001'::uuid, 'authenticated');

-- Resident A should see exactly their 2 tickets (TKT-2026-1001, TKT-2026-0972)
DO $$
DECLARE
    v_count INT;
BEGIN
    SELECT COUNT(*) INTO v_count FROM public.complaints;
    IF v_count <> 2 THEN
        RAISE EXCEPTION 'TEST 1.1 FAILED: Resident A saw % tickets (expected 2)', v_count;
    ELSE
        RAISE NOTICE 'TEST 1.1 PASSED: Resident A sees only their own 2 tickets.';
    END IF;
END $$;

-- Resident A attempts to read Resident B's ticket (TKT-2026-1002)
DO $$
DECLARE
    v_found BOOLEAN;
BEGIN
    SELECT EXISTS (SELECT 1 FROM public.complaints WHERE ticket_number = 'TKT-2026-1002') INTO v_found;
    IF v_found THEN
        RAISE EXCEPTION 'SECURITY BREACH 1.2: Resident A was able to read Resident B ticket!';
    ELSE
        RAISE NOTICE 'TEST 1.2 PASSED: Resident A cannot view Resident B ticket (0 rows returned).';
    END IF;
END $$;

-- Resident A attempts to UPDATE Resident B's ticket
DO $$
DECLARE
    v_rows INT;
BEGIN
    UPDATE public.complaints 
    SET description = 'Hacked by Resident A' 
    WHERE ticket_number = 'TKT-2026-1002';
    
    GET DIAGNOSTICS v_rows = ROW_COUNT;
    IF v_rows > 0 THEN
        RAISE EXCEPTION 'SECURITY BREACH 1.3: Resident A modified Resident B ticket!';
    ELSE
        RAISE NOTICE 'TEST 1.3 PASSED: Resident A cannot modify Resident B ticket (0 rows affected).';
    END IF;
END $$;

\echo '============================================================'
\echo 'TEST 2: Resident B (Rahul Verma) Tenant Privacy'
\echo '============================================================'
CALL test_as_user('00000000-0000-0000-0000-000000000002'::uuid, 'authenticated');

-- Resident B should see only their 1 ticket (TKT-2026-1002)
DO $$
DECLARE
    v_count INT;
BEGIN
    SELECT COUNT(*) INTO v_count FROM public.complaints;
    IF v_count <> 1 THEN
        RAISE EXCEPTION 'TEST 2.1 FAILED: Resident B saw % tickets (expected 1)', v_count;
    ELSE
        RAISE NOTICE 'TEST 2.1 PASSED: Resident B sees only their own 1 ticket.';
    END IF;
END $$;

-- Resident B attempts to read Resident A's ticket
DO $$
DECLARE
    v_found BOOLEAN;
BEGIN
    SELECT EXISTS (SELECT 1 FROM public.complaints WHERE ticket_number = 'TKT-2026-1001') INTO v_found;
    IF v_found THEN
        RAISE EXCEPTION 'SECURITY BREACH 2.2: Resident B was able to read Resident A ticket!';
    ELSE
        RAISE NOTICE 'TEST 2.2 PASSED: Resident B cannot view Resident A ticket.';
    END IF;
END $$;

\echo '============================================================'
\echo 'TEST 3: Anonymous Public User Privacy & Token Tracking'
\echo '============================================================'
CALL test_as_user(NULL, 'anon');

-- Anon user direct SELECT on complaints table should return 0 rows!
DO $$
DECLARE
    v_count INT;
BEGIN
    SELECT COUNT(*) INTO v_count FROM public.complaints;
    IF v_count > 0 THEN
        RAISE EXCEPTION 'SECURITY BREACH 3.1: Anonymous user was able to query % raw complaints!', v_count;
    ELSE
        RAISE NOTICE 'TEST 3.1 PASSED: Anonymous user cannot query raw complaints table directly (0 rows).';
    END IF;
END $$;

-- Anon user queries status using VALID secret token: 'demo_secret_token_12345'
DO $$
DECLARE
    v_data JSONB;
BEGIN
    v_data := public.get_anonymous_complaint_status('TKT-2026-ANON01', 'demo_secret_token_12345');
    IF v_data->>'ticket_number' = 'TKT-2026-ANON01' THEN
        RAISE NOTICE 'TEST 3.2 PASSED: Anonymous user successfully tracked status via valid cryptographic token.';
    ELSE
        RAISE EXCEPTION 'TEST 3.2 FAILED: Expected ticket data not returned.';
    END IF;
END $$;

-- Anon user attempts tracking with INVALID secret token: 'wrong_secret_123'
DO $$
DECLARE
    v_failed BOOLEAN := false;
    v_data JSONB;
BEGIN
    BEGIN
        v_data := public.get_anonymous_complaint_status('TKT-2026-ANON01', 'wrong_secret_123');
    EXCEPTION WHEN OTHERS THEN
        v_failed := true;
    END IF;

    IF v_failed THEN
        RAISE NOTICE 'TEST 3.3 PASSED: Invalid secret token was rejected with error.';
    ELSE
        RAISE EXCEPTION 'SECURITY BREACH 3.3: Invalid tracking token allowed access to ticket!';
    END IF;
END $$;

\echo '============================================================'
\echo 'TEST 4: Service Team (Rajesh Kumar) Scoped Access'
\echo '============================================================'
CALL test_as_user('00000000-0000-0000-0000-000000000003'::uuid, 'authenticated');

-- Service technician should see tickets in their assigned ward (North Ward)
DO $$
DECLARE
    v_count INT;
BEGIN
    SELECT COUNT(*) INTO v_count FROM public.complaints;
    IF v_count >= 2 THEN
        RAISE NOTICE 'TEST 4.1 PASSED: Technician sees % work orders in duty ward.', v_count;
    ELSE
        RAISE EXCEPTION 'TEST 4.1 FAILED: Technician saw only % work orders', v_count;
    END IF;
END $$;

\echo '============================================================'
\echo 'TEST 5: Central Administrator Oversight'
\echo '============================================================'
CALL test_as_user('00000000-0000-0000-0000-000000000004'::uuid, 'authenticated');

-- Admin should see all 4 complaints
DO $$
DECLARE
    v_count INT;
BEGIN
    SELECT COUNT(*) INTO v_count FROM public.complaints;
    IF v_count = 4 THEN
        RAISE NOTICE 'TEST 5.1 PASSED: Administrator has full oversight over all 4 complaints.';
    ELSE
        RAISE EXCEPTION 'TEST 5.1 FAILED: Admin saw % complaints (expected 4)', v_count;
    END IF;
END $$;

\echo '============================================================'
\echo 'ALL SECURITY & RLS TESTS PASSED SUCCESSFULLY!'
\echo '============================================================'

-- Rollback the transaction so test runs do not alter clean state
ROLLBACK;
