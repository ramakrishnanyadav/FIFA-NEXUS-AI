from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, EmailStr
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
    password: str
    role_name: str = "VOLUNTEER" # VOLUNTEER, SECURITY, VENUE_MANAGER

class UserResponse(UserBase):
    id: UUID
    role_id: UUID
    is_active: bool
    created_at: datetime

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None

# Telemetry Schemas
class TelemetryCreate(BaseModel):
    zone_id: UUID
    sensor_type: str = Field(..., description="Type of sensor: camera, turnstile, gate")
    count: int = Field(..., ge=0, description="Measured count of entities (occupancy, wait count)")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# Event Schemas
class OperationalEventCreate(BaseModel):
    zone_id: Optional[UUID] = None
    source: str = Field(..., description="Event publisher system name")
    event_type: str = Field(..., description="Type of operational event, e.g. CROWD_DENSITY_HIGH")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Typed event payload parameters")
    correlation_id: Optional[UUID] = None
    trace_id: Optional[str] = None

class OperationalEventResponse(SchemaBase):
    id: UUID
    zone_id: Optional[UUID]
    source: str
    event_type: str
    payload: Dict[str, Any]
    received_at: datetime
    correlation_id: UUID
    trace_id: Optional[str]

# Recommendation Schemas
class RecommendationResponse(SchemaBase):
    id: UUID
    trigger_event_id: UUID
    target_role: str
    candidate_actions: List[str]
    expected_impact: Dict[str, Any]
    validation_status: str
    policy_flags: List[str]
    prompt_version: str
    model_version: str
    knowledge_version: str
    confidence: float
    reasoning_summary: str
    reasoning_time_ms: Optional[float] = None
    generated_at: datetime

class RecommendationFeedback(BaseModel):
    accepted: bool
    applied: bool
    feedback_rating: int = Field(..., ge=1, le=5)
    feedback_comments: Optional[str] = None

# Task Schemas
class TaskResponse(SchemaBase):
    id: UUID
    recommendation_id: Optional[UUID]
    assigned_user_id: Optional[UUID]
    assigned_role: str
    details: str
    status: str
    created_at: datetime
    updated_at: datetime

class TaskUpdate(BaseModel):
    status: str = Field(..., description="New task status: ACKNOWLEDGED, STARTED, COMPLETED, CANCELLED")
