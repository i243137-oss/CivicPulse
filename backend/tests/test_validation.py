"""
Unit and integration tests for data validation, schema constraints, and parameter parsing.

Covers Assignment Section 7 (Testing and quality):
- Pydantic schema validation for ComplaintCreate, ComplaintStatusUpdate, and TriageResult.
- Boundary conditions: min/max length on complaint text (10-2000 chars) and location (3-200 chars).
- Contact string length boundaries (max 255 chars).
- Strict Enum validation: CategoryEnum, PriorityEnum, and StatusEnum.
- HTTP API parameter validation: page >= 1, 1 <= page_size <= 100, malformed UUID rejection.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.models.complaint import CategoryEnum, PriorityEnum, StatusEnum
from app.providers.triage.base import TriageResult
from app.schemas.complaint import ComplaintCreate, ComplaintStatusUpdate

# ==============================================================================
# 1. Pydantic Model Unit Validation Tests
# ==============================================================================


def test_complaint_create_text_length_boundaries() -> None:
    """Validate complaint description length boundaries (10 to 2000 chars)."""
    # 9 chars -> Fails (too short)
    with pytest.raises(ValidationError) as exc:
        ComplaintCreate(text="123456789", location="Valid Location")
    assert "text" in str(exc.value)

    # 10 chars -> Passes (minimum allowed)
    valid_min = ComplaintCreate(text="1234567890", location="Valid Location")
    assert valid_min.text == "1234567890"

    # 2000 chars -> Passes (maximum allowed)
    valid_max = ComplaintCreate(text="A" * 2000, location="Valid Location")
    assert len(valid_max.text) == 2000

    # 2001 chars -> Fails (exceeds limit)
    with pytest.raises(ValidationError) as exc:
        ComplaintCreate(text="A" * 2001, location="Valid Location")
    assert "text" in str(exc.value)


def test_complaint_create_location_length_boundaries() -> None:
    """Validate location length boundaries (3 to 200 chars)."""
    # 2 chars -> Fails
    with pytest.raises(ValidationError) as exc:
        ComplaintCreate(text="Valid complaint description", location="12")
    assert "location" in str(exc.value)

    # 3 chars -> Passes
    valid_min = ComplaintCreate(text="Valid complaint description", location="123")
    assert valid_min.location == "123"

    # 200 chars -> Passes
    valid_max = ComplaintCreate(text="Valid complaint description", location="L" * 200)
    assert len(valid_max.location) == 200

    # 201 chars -> Fails
    with pytest.raises(ValidationError) as exc:
        ComplaintCreate(text="Valid complaint description", location="L" * 201)
    assert "location" in str(exc.value)


def test_complaint_create_reporter_contact_boundaries() -> None:
    """Validate optional reporter_contact max length constraint (255 chars)."""
    # None -> Passes
    c1 = ComplaintCreate(
        text="Valid complaint text", location="Valid Location", reporter_contact=None
    )
    assert c1.reporter_contact is None

    # 255 chars -> Passes
    c2 = ComplaintCreate(
        text="Valid complaint text", location="Valid Location", reporter_contact="c" * 255
    )
    assert c2.reporter_contact is not None
    assert len(c2.reporter_contact) == 255

    # 256 chars -> Fails
    with pytest.raises(ValidationError) as exc:
        ComplaintCreate(
            text="Valid complaint text", location="Valid Location", reporter_contact="c" * 256
        )
    assert "reporter_contact" in str(exc.value)


def test_complaint_create_enum_validation() -> None:
    """Validate category and priority enums in ComplaintCreate."""
    # Valid enum strings
    c = ComplaintCreate.model_validate(
        {
            "text": "Valid complaint text",
            "location": "Valid Location",
            "category": "water",
            "priority": "high",
        }
    )
    assert c.category == CategoryEnum.WATER
    assert c.priority == PriorityEnum.HIGH

    # Invalid category
    with pytest.raises(ValidationError) as exc:
        ComplaintCreate.model_validate(
            {
                "text": "Valid complaint text",
                "location": "Valid Location",
                "category": "astronomy",
            }
        )
    assert "category" in str(exc.value)

    # Invalid priority
    with pytest.raises(ValidationError) as exc:
        ComplaintCreate.model_validate(
            {
                "text": "Valid complaint text",
                "location": "Valid Location",
                "priority": "ultra_emergency",
            }
        )
    assert "priority" in str(exc.value)


def test_complaint_status_update_validation() -> None:
    """Validate status update schema accepts valid StatusEnum values and rejects others."""
    # Valid transitions
    for status_val in [StatusEnum.IN_PROGRESS, StatusEnum.RESOLVED, StatusEnum.REJECTED]:
        update = ComplaintStatusUpdate(status=status_val)
        assert update.status == status_val

    # Invalid status string
    with pytest.raises(ValidationError) as exc:
        ComplaintStatusUpdate.model_validate({"status": "pending_approval"})
    assert "status" in str(exc.value)


def test_triage_result_schema_normalization_and_constraints() -> None:
    """Validate TriageResult normalization, confidence bounds, and summary truncation."""
    # Normalization of 'critical' -> 'high' and 'medium' -> 'normal'
    t1 = TriageResult.model_validate(
        {
            "category": "roads",
            "priority": "critical",
            "summary": "Collapsed road bridge",
            "confidence": 0.95,
        }
    )
    assert t1.priority == PriorityEnum.HIGH

    t2 = TriageResult.model_validate(
        {
            "category": "sanitation",
            "priority": "medium",
            "summary": "Overflowing dumpster",
            "confidence": 0.85,
        }
    )
    assert t2.priority == PriorityEnum.NORMAL

    # Oversized summary automatically truncated with ellipsis to 140 chars
    long_summary = "X" * 150
    t3 = TriageResult.model_validate(
        {
            "category": "water",
            "priority": "low",
            "summary": long_summary,
            "confidence": 0.5,
        }
    )
    assert len(t3.summary) == 140
    assert t3.summary.endswith("...")

    # Confidence must be between 0.0 and 1.0
    with pytest.raises(ValidationError):
        TriageResult.model_validate(
            {
                "category": "water",
                "priority": "low",
                "summary": "Valid summary",
                "confidence": 1.5,
            }
        )

    with pytest.raises(ValidationError):
        TriageResult.model_validate(
            {
                "category": "water",
                "priority": "low",
                "summary": "Valid summary",
                "confidence": -0.1,
            }
        )


# ==============================================================================
# 2. HTTP Route Parameter & Body Validation (Integration)
# ==============================================================================


def test_api_create_complaint_missing_required_fields(client: TestClient) -> None:
    """POST /api/complaints returns 422 Unprocessable Entity when required fields are missing."""
    # Missing location
    res1 = client.post("/api/complaints", json={"text": "Water pipeline burst causing damage."})
    assert res1.status_code == 422
    assert any("location" in loc["loc"] for loc in res1.json()["detail"])

    # Missing text
    res2 = client.post("/api/complaints", json={"location": "Sector G-10/2"})
    assert res2.status_code == 422
    assert any("text" in loc["loc"] for loc in res2.json()["detail"])

    # Empty payload
    res3 = client.post("/api/complaints", json={})
    assert res3.status_code == 422


def test_api_list_complaints_pagination_bounds(client: TestClient) -> None:
    """GET /api/complaints validates page >= 1 and 1 <= page_size <= 100."""
    # page = 0 -> 422
    r1 = client.get("/api/complaints?page=0")
    assert r1.status_code == 422
    assert any("page" in loc["loc"] for loc in r1.json()["detail"])

    # page = -5 -> 422
    r2 = client.get("/api/complaints?page=-5")
    assert r2.status_code == 422

    # page_size = 0 -> 422
    r3 = client.get("/api/complaints?page_size=0")
    assert r3.status_code == 422
    assert any("page_size" in loc["loc"] for loc in r3.json()["detail"])

    # page_size = 101 -> 422 (max 100)
    r4 = client.get("/api/complaints?page_size=101")
    assert r4.status_code == 422
    assert any("page_size" in loc["loc"] for loc in r4.json()["detail"])

    # Valid boundaries: page=1, page_size=100 -> 200 OK
    r5 = client.get("/api/complaints?page=1&page_size=100")
    assert r5.status_code == 200


def test_api_list_complaints_filter_enums(client: TestClient) -> None:
    """GET /api/complaints rejects unrecognized category, priority, or status filters."""
    # Invalid category filter
    r1 = client.get("/api/complaints?category=spacecraft")
    assert r1.status_code == 422

    # Invalid priority filter
    r2 = client.get("/api/complaints?priority=catastrophic")
    assert r2.status_code == 422

    # Invalid status filter
    r3 = client.get("/api/complaints?status=abandoned")
    assert r3.status_code == 422


def test_api_get_complaint_malformed_uuid(client: TestClient) -> None:
    """GET /api/complaints/{id} rejects malformed UUID with 422."""
    res = client.get("/api/complaints/not-a-valid-uuid")
    assert res.status_code == 422
    assert any("complaint_id" in loc["loc"] for loc in res.json()["detail"])


def test_api_update_complaint_status_malformed_uuid_and_payload(client: TestClient) -> None:
    """PATCH /api/complaints/{id}/status rejects non-UUID paths and invalid payloads."""
    # Malformed UUID in path
    r1 = client.patch("/api/complaints/12345/status", json={"status": "in_progress"})
    assert r1.status_code == 422

    # Valid UUID but invalid status enum
    valid_uuid = str(uuid.uuid4())
    r2 = client.patch(f"/api/complaints/{valid_uuid}/status", json={"status": "invalid_status"})
    assert r2.status_code == 422

    # Valid UUID but empty body
    r3 = client.patch(f"/api/complaints/{valid_uuid}/status", json={})
    assert r3.status_code == 422


# ==============================================================================
# 3. Application Security & CORS Validation Tests (Phase 11)
# ==============================================================================


def test_cors_wildcard_with_credentials_rejected() -> None:
    """Settings rejects wildcard CORS origins when allow_credentials is True."""
    from app.core.config import Settings

    with pytest.raises(ValidationError) as exc:
        Settings(CORS_ORIGINS=["*"], CORS_ALLOW_CREDENTIALS=True)
    assert "wildcard CORS_ORIGINS" in str(exc.value)


def test_cors_wildcard_in_production_rejected() -> None:
    """Settings rejects wildcard CORS origins in production environment."""
    from app.core.config import Settings

    with pytest.raises(ValidationError) as exc:
        Settings(
            ENVIRONMENT="production",
            CORS_ORIGINS=["*"],
            CORS_ALLOW_CREDENTIALS=False,
        )
    assert "prohibited in production" in str(exc.value)


def test_cors_comma_separated_origins_parsed() -> None:
    """Settings correctly parses comma-separated CORS origins string."""
    from app.core.config import Settings

    s = Settings(
        CORS_ORIGINS="http://frontend.local,http://dashboard.local",
        CORS_ALLOW_CREDENTIALS=True,
    )
    assert s.CORS_ORIGINS == ["http://frontend.local", "http://dashboard.local"]
