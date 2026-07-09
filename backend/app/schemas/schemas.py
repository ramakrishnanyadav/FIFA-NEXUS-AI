from datetime import datetime, UTC
from typing import Any, Literal
from pydantic import BaseModel, Field, EmailStr, field_validator, field_serializer
from uuid import UUID

# Shared Config
class SchemaBase(BaseModel):
    model_config = {
        "from_attributes": True,
        "protected_namespaces": ()
    }

# User & Auth Schemas
class UserBase(SchemaBase):
    username: str
    email: EmailStr

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, description="User password (minimum 8 characters)")
    role_name: Literal["VOLUNTEER", "SECURITY", "VENUE_MANAGER", "DISPATCHER", "FAN", "ACCESSIBILITY_STAFF"] = "VOLUNTEER"

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        _ = cls  # Reference cls to satisfy Vulture unused-variable check
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number")
        return v

class UserResponse(UserBase):
    id: UUID
    role_id: UUID
    is_active: bool
    created_at: datetime

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None
    role: str | None = None

# Telemetry Schemas
class TelemetryCreate(BaseModel):
    zone_id: UUID
    sensor_type: Literal["camera", "turnstile", "gate"] = Field(..., description="Type of sensor: camera, turnstile, gate")
    count: int = Field(..., ge=0, description="Measured count of entities (occupancy, wait count)")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = {
        "json_schema_extra": {
            "example": {
                "zone_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
                "sensor_type": "camera",
                "count": 850,
                "timestamp": "2026-07-09T15:00:00Z"
            }
        }
    }

# Event Schemas
class OperationalEventCreate(BaseModel):
    zone_id: UUID | None = None
    source: str = Field(..., description="Event publisher system name")
    event_type: Literal["CROWD_DENSITY_HIGH", "VOLUNTEER_DISPATCH", "SECURITY_ALERT", "INCIDENT_DISPATCH", "SYSTEM_UPDATE"] = Field(..., description="Type of operational event")
    payload: dict[str, Any] = Field(default_factory=dict, description="Typed event payload parameters")
    correlation_id: UUID | None = None
    trace_id: str | None = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "zone_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
                "source": "sensor:camera:9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
                "event_type": "CROWD_DENSITY_HIGH",
                "payload": {
                    "current_occupancy": 850,
                    "safe_capacity": 1000,
                    "occupancy_ratio": 0.85
                },
                "correlation_id": "e3e8f810-705a-4bbf-a01a-84fb5f448b11"
            }
        }
    }

class OperationalEventResponse(SchemaBase):
    id: UUID
    zone_id: UUID | None
    source: str
    event_type: Literal["CROWD_DENSITY_HIGH", "VOLUNTEER_DISPATCH", "SECURITY_ALERT", "INCIDENT_DISPATCH", "SYSTEM_UPDATE"]
    payload: dict[str, Any]
    received_at: datetime
    correlation_id: UUID
    trace_id: str | None

    @field_serializer("received_at")
    def serialize_received_at(self, dt: datetime) -> str:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.isoformat().replace("+00:00", "Z")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "c7fde61b-9f1e-4509-88c9-9430e79cde66",
                "zone_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
                "source": "sensor:camera:9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
                "event_type": "CROWD_DENSITY_HIGH",
                "payload": {
                    "current_occupancy": 850,
                    "safe_capacity": 1000,
                    "occupancy_ratio": 0.85
                },
                "received_at": "2026-07-09T15:00:05Z",
                "correlation_id": "e3e8f810-705a-4bbf-a01a-84fb5f448b11"
            }
        }
    }

# Recommendation Schemas
class RecommendationResponse(SchemaBase):
    id: UUID
    trigger_event_id: UUID
    target_role: Literal["VOLUNTEER", "SECURITY", "VENUE_MANAGER", "DISPATCHER", "FAN", "ACCESSIBILITY_STAFF"]
    candidate_actions: list[str]
    expected_impact: dict[str, Any]
    validation_status: Literal["GENERATED", "VALIDATED", "APPROVED", "REJECTED", "POLICY_VIOLATION"]
    policy_flags: list[str]
    prompt_version: str
    model_version: str
    knowledge_version: str
    confidence: float
    reasoning_summary: str
    reasoning_time_ms: float | None = None
    generated_at: datetime

    @field_serializer("generated_at")
    def serialize_generated_at(self, dt: datetime) -> str:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.isoformat().replace("+00:00", "Z")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "a4b1dec3-a6d1-4bad-92bc-7bfcd83d91cf",
                "trigger_event_id": "c7fde61b-9f1e-4509-88c9-9430e79cde66",
                "target_role": "VOLUNTEER",
                "candidate_actions": [
                    "Open additional turnstiles at Gate B to relieve pressure on Gate A.",
                    "Deploy mobile signs redirecting arriving fans from Gate A to Gate B."
                ],
                "expected_impact": {
                    "wait_time_reduction_min": 12,
                    "co2_saved_kg": 4.5
                },
                "validation_status": "VALIDATED",
                "policy_flags": [],
                "prompt_version": "sop_incident_reasoning:v2",
                "model_version": "gpt-4o-mini:2024-07-18",
                "knowledge_version": "sop_handbook_miami_2026_v1",
                "confidence": 0.95,
                "reasoning_summary": "Crowd density at Gate A is at critical levels. Directing volunteers to deploy signs and open Gate B will distribute the load effectively.",
                "reasoning_time_ms": 145.2,
                "generated_at": "2026-07-09T15:00:07Z"
            }
        }
    }

class RecommendationFeedback(BaseModel):
    accepted: bool
    applied: bool
    feedback_rating: int = Field(..., ge=1, le=5)
    feedback_comments: str | None = None

# Task Schemas
class TaskResponse(SchemaBase):
    id: UUID
    recommendation_id: UUID | None
    assigned_user_id: UUID | None
    assigned_role: Literal["VOLUNTEER", "SECURITY", "VENUE_MANAGER", "DISPATCHER", "FAN", "ACCESSIBILITY_STAFF"]
    details: str
    status: Literal["PENDING", "DISPATCHED", "ACKNOWLEDGED", "STARTED", "COMPLETED", "CANCELLED"]
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, dt: datetime) -> str:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.isoformat().replace("+00:00", "Z")

    @field_serializer("updated_at")
    def serialize_updated_at(self, dt: datetime) -> str:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.isoformat().replace("+00:00", "Z")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "e4fde72c-81b3-4f2c-98d9-e93c8b9d88cc",
                "recommendation_id": "a4b1dec3-a6d1-4bad-92bc-7bfcd83d91cf",
                "assigned_user_id": None,
                "assigned_role": "VOLUNTEER",
                "details": "Deploy mobile signs redirecting arriving fans from Gate A to Gate B.",
                "status": "DISPATCHED",
                "created_at": "2026-07-09T15:00:08Z",
                "updated_at": "2026-07-09T15:00:08Z"
            }
        }
    }

class TaskUpdate(BaseModel):
    status: Literal["PENDING", "DISPATCHED", "ACKNOWLEDGED", "STARTED", "COMPLETED", "CANCELLED"] = Field(..., description="New task status")
