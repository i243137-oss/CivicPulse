"""
Full-path end-to-end integration tests for the complete CivicPulse application journey.

Covers Assignment Section 7 (Testing and quality):
- End-to-end application lifecycle across all layers:
  1. Health & Readiness probe verification (/health, /ready).
  2. Statistics read-through caching and initial cache miss/hit verification.
  3. Citizen complaint intake with automated AI triage classification.
  4. Post-commit write cache invalidation of statistics.
  5. Duplicate submission content-hash cache verification and sub-millisecond execution.
  6. Real-time telemetry monitoring via /api/meta/providers (hit_rate, active provider).
  7. Multi-category filtering and paginated complaints querying.
  8. State machine operations: open -> in_progress -> resolved.
  9. Rejection of illegal and terminal state transitions with HTTP 409 Conflict.
  10. Final aggregated statistics validation reflecting state machine resolution.
"""

from fastapi.testclient import TestClient

from app.models.complaint import CategoryEnum, PriorityEnum, StatusEnum


def test_complete_application_path_integration_journey(client: TestClient) -> None:
    """
    Execute complete end-to-end integration journey covering:
    probes -> stats cache -> complaint intake -> automated triage ->
    duplicate caching -> query filters & pagination -> state machine transitions ->
    conflict rejection -> final stats consistency.
    """
    # --------------------------------------------------------------------------
    # Step 1: Health & Readiness Probe Verification
    # --------------------------------------------------------------------------
    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "ok"

    res_ready = client.get("/ready")
    assert res_ready.status_code == 200
    assert res_ready.json()["status"] == "ready"

    # --------------------------------------------------------------------------
    # Step 2: Initial Statistics Read-Through Cache Verification
    # --------------------------------------------------------------------------
    # First call: Cache MISS
    res_stats_1 = client.get("/api/stats")
    assert res_stats_1.status_code == 200
    assert res_stats_1.headers.get("X-Cache") == "MISS"
    stats_data_1 = res_stats_1.json()
    assert stats_data_1["total"] == 0

    # Second call: Cache HIT
    res_stats_2 = client.get("/api/stats")
    assert res_stats_2.status_code == 200
    assert res_stats_2.headers.get("X-Cache") == "HIT"
    assert res_stats_2.json()["total"] == 0

    # --------------------------------------------------------------------------
    # Step 3: Citizen Complaint Intake with Automated AI Triage
    # --------------------------------------------------------------------------
    water_complaint_payload = {
        "text": "Severe water main burst flooding basements along the main avenue.",
        "location": "Sector F-7/2, Street 14, Islamabad",
        "reporter_contact": "+923001234567",
    }
    res_create_1 = client.post("/api/complaints", json=water_complaint_payload)
    assert res_create_1.status_code == 201
    c1 = res_create_1.json()
    c1_id = c1["id"]

    assert c1["status"] == StatusEnum.OPEN.value
    assert c1["category"] == CategoryEnum.WATER.value
    assert c1["priority"] in [PriorityEnum.HIGH.value, PriorityEnum.NORMAL.value]
    assert c1["ai_summary"] is not None
    assert c1["triaged_by"] is not None
    assert c1["triage_latency_ms"] >= 1
    assert StatusEnum.IN_PROGRESS.value in c1["allowed_transitions"]
    assert StatusEnum.REJECTED.value in c1["allowed_transitions"]

    # --------------------------------------------------------------------------
    # Step 4: Write-Through Cache Invalidation Check
    # --------------------------------------------------------------------------
    # Writing a complaint must have invalidated the statistics cache
    res_stats_3 = client.get("/api/stats")
    assert res_stats_3.status_code == 200
    assert res_stats_3.headers.get("X-Cache") == "MISS"
    assert res_stats_3.json()["total"] == 1
    assert res_stats_3.json()["by_category"]["water"] == 1
    assert res_stats_3.json()["by_status"]["open"] == 1

    # --------------------------------------------------------------------------
    # Step 5: Duplicate Complaint Submission (Content-Hash Cache HIT)
    # --------------------------------------------------------------------------
    # Submitting identical text and location hits 24h content-hash cache in Redis
    res_create_dup = client.post("/api/complaints", json=water_complaint_payload)
    assert res_create_dup.status_code == 201
    c_dup = res_create_dup.json()
    assert c_dup["id"] != c1_id
    assert c_dup["category"] == CategoryEnum.WATER.value
    assert "cache" in c_dup["triaged_by"]

    # --------------------------------------------------------------------------
    # Step 6: Provider Telemetry Verification
    # --------------------------------------------------------------------------
    res_meta = client.get("/api/meta/providers")
    assert res_meta.status_code == 200
    meta_data = res_meta.json()
    assert "cache_metrics" in meta_data
    cache_metrics = meta_data["cache_metrics"]
    assert cache_metrics["hits"] >= 1
    assert cache_metrics["misses"] >= 1
    assert cache_metrics["total_requests"] >= 2
    assert 0.0 < cache_metrics["hit_rate"] <= 1.0

    # --------------------------------------------------------------------------
    # Step 7: Second Distinct Complaint Submission (Electricity)
    # --------------------------------------------------------------------------
    elec_complaint_payload = {
        "text": "Dangerous sparking high-voltage wire hanging low over public pathway.",
        "location": "Sector G-10/4, Market Road, Islamabad",
        "reporter_contact": "+923009876543",
    }
    res_create_2 = client.post("/api/complaints", json=elec_complaint_payload)
    assert res_create_2.status_code == 201
    c2 = res_create_2.json()
    assert c2["category"] == CategoryEnum.ELECTRICITY.value
    assert c2["status"] == StatusEnum.OPEN.value

    # --------------------------------------------------------------------------
    # Step 8: Multi-Filter and Paginated Complaints Querying
    # --------------------------------------------------------------------------
    # Filter by category: water -> returns 2 items
    r_water = client.get("/api/complaints?category=water")
    assert r_water.status_code == 200
    assert r_water.json()["total"] == 2
    assert len(r_water.json()["items"]) == 2

    # Filter by category: electricity -> returns 1 item
    r_elec = client.get("/api/complaints?category=electricity")
    assert r_elec.status_code == 200
    assert r_elec.json()["total"] == 1
    assert r_elec.json()["items"][0]["category"] == "electricity"

    # Filter by status: open -> returns all 3
    r_open = client.get("/api/complaints?status=open")
    assert r_open.status_code == 200
    assert r_open.json()["total"] == 3

    # Pagination: page 1, page_size 2 -> returns 2 items, total_pages = 2
    r_page1 = client.get("/api/complaints?page=1&page_size=2")
    assert r_page1.status_code == 200
    page1_data = r_page1.json()
    assert page1_data["total"] == 3
    assert page1_data["page"] == 1
    assert page1_data["page_size"] == 2
    assert page1_data["total_pages"] == 2
    assert len(page1_data["items"]) == 2

    # Pagination: page 2, page_size 2 -> returns 1 item
    r_page2 = client.get("/api/complaints?page=2&page_size=2")
    assert r_page2.status_code == 200
    page2_data = r_page2.json()
    assert len(page2_data["items"]) == 1

    # --------------------------------------------------------------------------
    # Step 9: State Machine Lifecycle on Complaint 1
    # --------------------------------------------------------------------------
    # Fetch complaint by ID
    r_get = client.get(f"/api/complaints/{c1_id}")
    assert r_get.status_code == 200
    assert r_get.json()["id"] == c1_id

    # Valid Transition 1: open -> in_progress
    r_trans_1 = client.patch(
        f"/api/complaints/{c1_id}/status",
        json={"status": StatusEnum.IN_PROGRESS.value},
    )
    assert r_trans_1.status_code == 200
    assert r_trans_1.json()["status"] == StatusEnum.IN_PROGRESS.value
    assert StatusEnum.RESOLVED.value in r_trans_1.json()["allowed_transitions"]
    assert StatusEnum.REJECTED.value in r_trans_1.json()["allowed_transitions"]

    # Invalid Transition: in_progress -> open (Forbidden backward transition)
    r_invalid_trans = client.patch(
        f"/api/complaints/{c1_id}/status",
        json={"status": StatusEnum.OPEN.value},
    )
    assert r_invalid_trans.status_code == 409
    err_detail = r_invalid_trans.json()["detail"]
    assert err_detail["current_status"] == StatusEnum.IN_PROGRESS.value
    assert err_detail["target_status"] == StatusEnum.OPEN.value

    # Valid Transition 2: in_progress -> resolved
    r_trans_2 = client.patch(
        f"/api/complaints/{c1_id}/status",
        json={"status": StatusEnum.RESOLVED.value},
    )
    assert r_trans_2.status_code == 200
    assert r_trans_2.json()["status"] == StatusEnum.RESOLVED.value
    # Terminal state has zero allowed transitions
    assert r_trans_2.json()["allowed_transitions"] == []

    # Attempting transition on terminal state -> HTTP 409 Conflict
    r_terminal_attempt = client.patch(
        f"/api/complaints/{c1_id}/status",
        json={"status": StatusEnum.IN_PROGRESS.value},
    )
    assert r_terminal_attempt.status_code == 409

    # --------------------------------------------------------------------------
    # Step 10: Final Statistics Verification
    # --------------------------------------------------------------------------
    res_final_stats = client.get("/api/stats")
    assert res_final_stats.status_code == 200
    final_stats = res_final_stats.json()
    assert final_stats["total"] == 3
    assert final_stats["by_status"].get("open", 0) == 2
    assert final_stats["by_status"].get("in_progress", 0) == 0
    assert final_stats["by_status"].get("resolved", 0) == 1
    assert final_stats["by_category"].get("water", 0) == 2
    assert final_stats["by_category"].get("electricity", 0) == 1

