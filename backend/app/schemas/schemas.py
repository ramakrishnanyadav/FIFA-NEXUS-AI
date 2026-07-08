from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field, EmailStr, field_validator
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
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# Event Schemas
class OperationalEventCreate(BaseModel):
    zone_id: UUID | None = None
    source: str = Field(..., description="Event publisher system name")
    event_type: Literal["CROWD_DENSITY_HIGH", "VOLUNTEER_DISPATCH", "SECURITY_ALERT", "INCIDENT_DISPATCH", "SYSTEM_UPDATE"] = Field(..., description="Type of operational event")
    payload: dict[str, Any] = Field(default_factory=dict, description="Typed event payload parameters")
    correlation_id: UUID | None = None
    trace_id: str | None = None

class OperationalEventResponse(SchemaBase):
    id: UUID
    zone_id: UUID | None
    source: str
    event_type: Literal["CROWD_DENSITY_HIGH", "VOLUNTEER_DISPATCH", "SECURITY_ALERT", "INCIDENT_DISPATCH", "SYSTEM_UPDATE"]
    payload: dict[str, Any]
    received_at: datetime
    correlation_id: UUID
    trace_id: str | None

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

class TaskUpdate(BaseModel):
    status: Literal["PENDING", "DISPATCHED", "ACKNOWLEDGED", "STARTED", "COMPLETED", "CANCELLED"] = Field(..., description="New task status")

