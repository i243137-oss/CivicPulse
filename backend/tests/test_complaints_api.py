"""
Integration tests for the CivicPulse complaints API endpoints.

Covers exact routes required by the assignment specification:
- POST /api/complaints (201 / 422 field-level validation)
- GET /api/complaints/{id} (200 / 404)
- GET /api/complaints (filtering, pagination, total)
- PATCH /api/complaints/{id}/status (state machine enforcement, 409 on invalid transition)
- GET /api/stats (aggregates)
- GET /api/meta/providers (provider observability)
"""

import uuid

from fastapi.testclient import TestClient


def test_post_complaint_creates_and_triages(client: TestClient) -> None:
    payload = {
        "text": "Broken water main leaking clean water all over Street 5 near market.",
        "location": "Sector F-6/2, Street 5, Islamabad",
        "reporter_contact": "+923001234567",
    }
    response = client.post("/api/complaints", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert "id" in data
    assert data["text"] == payload["text"]
    assert data["location"] == payload["location"]
    assert data["category"] == "water"
    assert data["status"] == "open"
    assert data["triaged_by"] is not None
    assert data["ai_summary"] is not None
    assert "created_at" in data
    assert "updated_at" in data


def test_post_complaint_validation_errors(client: TestClient) -> None:
    # Text too short (< 10 characters)
    short_text_payload = {
        "text": "Too short",
        "location": "Valid Location Street",
    }
    res1 = client.post("/api/complaints", json=short_text_payload)
    assert res1.status_code == 422
    err1 = res1.json()
    assert any("text" in loc["loc"] for loc in err1["detail"])

    # Location too short (< 3 characters)
    short_loc_payload = {
        "text": "Valid complaint description with enough characters.",
        "location": "Ab",
    }
    res2 = client.post("/api/complaints", json=short_loc_payload)
    assert res2.status_code == 422
    err2 = res2.json()
    assert any("location" in loc["loc"] for loc in err2["detail"])


def test_get_complaint_by_id(client: TestClient) -> None:
    # Create complaint
    create_res = client.post(
        "/api/complaints",
        json={
            "text": "Dangerous sparking transformer near neighborhood park.",
            "location": "Sector G-8/3 Park Lane",
        },
    )
    cid = create_res.json()["id"]

    # Fetch by ID
    get_res = client.get(f"/api/complaints/{cid}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == cid
    assert get_res.json()["category"] == "electricity"


def test_get_complaint_not_found(client: TestClient) -> None:
    non_existent = str(uuid.uuid4())
    res = client.get(f"/api/complaints/{non_existent}")
    assert res.status_code == 404
    assert f"Complaint with ID '{non_existent}' was not found." in res.json()["detail"]


def test_list_complaints_with_filtering_and_pagination(client: TestClient) -> None:
    # Seed 3 distinct complaints
    client.post(
        "/api/complaints",
        json={
            "text": "Sanitation problem: garbage dump overflowing near school.",
            "location": "Sector I-10/1, Islamabad",
            "category": "sanitation",
            "priority": "normal",
        },
    )
    client.post(
        "/api/complaints",
        json={
            "text": "Pothole on main road causing accidents every evening.",
            "location": "Murree Road, Rawalpindi",
            "category": "roads",
            "priority": "high",
        },
    )
    client.post(
        "/api/complaints",
        json={
            "text": "Streetlight fixture broken and dark corner dangerous.",
            "location": "Sector F-11/2, Islamabad",
            "category": "streetlights",
            "priority": "low",
        },
    )

    # Unfiltered list
    res_all = client.get("/api/complaints?page=1&page_size=10")
    assert res_all.status_code == 200
    body = res_all.json()
    assert body["total"] == 3
    assert len(body["items"]) == 3
    assert body["page"] == 1
    assert body["total_pages"] == 1

    # Filter by category
    res_cat = client.get("/api/complaints?category=sanitation")
    assert res_cat.status_code == 200
    assert res_cat.json()["total"] == 1
    assert res_cat.json()["items"][0]["category"] == "sanitation"

    # Filter by priority
    res_prio = client.get("/api/complaints?priority=high")
    assert res_prio.status_code == 200
    assert res_prio.json()["total"] == 1
    assert res_prio.json()["items"][0]["priority"] == "high"


def test_patch_complaint_status_state_machine_valid(client: TestClient) -> None:
    # Create open complaint
    create_res = client.post(
        "/api/complaints",
        json={
            "text": "Water pipeline leak on main road causing mud pools.",
            "location": "Sector G-10/4, Islamabad",
        },
    )
    cid = create_res.json()["id"]

    # Transition open -> in_progress (allowed)
    patch_res = client.patch(
        f"/api/complaints/{cid}/status",
        json={"status": "in_progress"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "in_progress"

    # Transition in_progress -> resolved (allowed)
    resolve_res = client.patch(
        f"/api/complaints/{cid}/status",
        json={"status": "resolved"},
    )
    assert resolve_res.status_code == 200
    assert resolve_res.json()["status"] == "resolved"


def test_patch_complaint_status_state_machine_invalid_returns_409(client: TestClient) -> None:
    # Create open complaint
    create_res = client.post(
        "/api/complaints",
        json={
            "text": "Damaged streetlight post outside house number 12.",
            "location": "Sector F-7/3, Islamabad",
        },
    )
    cid = create_res.json()["id"]

    # Attempt illegal transition: open -> resolved (must go through in_progress)
    illegal_res = client.patch(
        f"/api/complaints/{cid}/status",
        json={"status": "resolved"},
    )
    assert illegal_res.status_code == 409
    detail = illegal_res.json()["detail"]
    assert "Invalid status transition from 'open' to 'resolved'" in detail["message"]
    assert detail["current_status"] == "open"
    assert detail["target_status"] == "resolved"


def test_patch_complaint_status_terminal_states_return_409(client: TestClient) -> None:
    # Create and reject complaint (open -> rejected)
    create_res = client.post(
        "/api/complaints",
        json={
            "text": "Spam or irrelevant submission that gets rejected.",
            "location": "Unknown coordinates",
        },
    )
    cid = create_res.json()["id"]
    reject_res = client.patch(
        f"/api/complaints/{cid}/status",
        json={"status": "rejected"},
    )
    assert reject_res.status_code == 200

    # Rejected is terminal; attempt rejected -> open
    reopen_res = client.patch(
        f"/api/complaints/{cid}/status",
        json={"status": "open"},
    )
    assert reopen_res.status_code == 409
    detail = reopen_res.json()["detail"]
    assert "Invalid status transition from 'rejected' to 'open'" in detail["message"]


def test_get_stats_aggregates(client: TestClient) -> None:
    # Seed sample complaints
    client.post(
        "/api/complaints",
        json={
            "text": "Major water leak flooding residential lane.",
            "location": "Sector G-6/1",
            "category": "water",
            "priority": "high",
        },
    )
    client.post(
        "/api/complaints",
        json={
            "text": "Transformer issue causing frequent blackouts.",
            "location": "Sector G-6/2",
            "category": "electricity",
            "priority": "normal",
        },
    )

    res = client.get("/api/stats")
    assert res.status_code == 200
    stats = res.json()
    assert stats["total"] == 2
    assert stats["by_status"].get("open") == 2
    assert stats["by_category"].get("water") == 1
    assert stats["by_category"].get("electricity") == 1
    assert stats["by_priority"].get("high") == 1
    assert stats["by_priority"].get("normal") == 1


def test_get_meta_providers(client: TestClient) -> None:
    res = client.get("/api/meta/providers")
    assert res.status_code == 200
    data = res.json()
    assert "active_provider" in data
    assert "recent_outcomes" in data
