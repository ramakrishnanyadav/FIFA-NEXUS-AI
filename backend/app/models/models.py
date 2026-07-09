from datetime import datetime, UTC

def _now_utc():
    return datetime.now(UTC)
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Table,
    Text,
    UniqueConstraint,
    Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from backend.app.core.database import Base, USE_SQLITE

if USE_SQLITE:
    from sqlalchemy import JSON as SqliteJSON
    StadiumLocationType = String(100)
    ZoneBoundaryType = String(500)
    ArrayColumnType = SqliteJSON
    JSONColumnType = SqliteJSON
else:
    StadiumLocationType = Geometry(geometry_type='POINT', srid=4326)
    ZoneBoundaryType = Geometry(geometry_type='POLYGON', srid=4326)
    ArrayColumnType = ARRAY(Text)
    JSONColumnType = JSONB



# Association Table for Role-Permissions (Many-to-Many)
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", UUID(as_uuid=True), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)
)

class Role(Base):
    __tablename__ = "roles"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)

    # Relationships
    permissions = relationship("Permission", secondary=role_permissions, back_populates="roles")
    users = relationship("User", back_populates="role")


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    code = Column(String(100), unique=True, nullable=False)
    description = Column(String(200), nullable=False)

    # Relationships
    roles = relationship("Role", secondary=role_permissions, back_populates="permissions")


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now_utc, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    role = relationship("Role", back_populates="users")
    tasks = relationship("Task", back_populates="assigned_user")
    audit_logs = relationship("AuditLog", back_populates="user")


class Stadium(Base):
    __tablename__ = "stadiums"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    capacity = Column(Integer, nullable=False)
    location = Column(StadiumLocationType, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now_utc, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    zones = relationship("Zone", back_populates="stadium")


class Zone(Base):
    __tablename__ = "zones"
    __table_args__ = (UniqueConstraint("stadium_id", "name", name="uq_stadium_zone_name"),)

    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    stadium_id = Column(UUID(as_uuid=True), ForeignKey("stadiums.id", ondelete="RESTRICT"), nullable=False)
    name = Column(String(100), nullable=False)
    zone_type = Column(String(50), nullable=False) # GATE, CONCOURSE, STANDS, PARKING, TRANSPORT_HUB
    safe_capacity = Column(Integer, nullable=False)
    current_occupancy = Column(Integer, default=0, nullable=False)
    boundary = Column(ZoneBoundaryType, nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    stadium = relationship("Stadium", back_populates="zones")
    occupancy_snapshots = relationship("ZoneOccupancySnapshot", back_populates="zone")
    operational_events = relationship("OperationalEvent", back_populates="zone")


class ZoneOccupancySnapshot(Base):
    __tablename__ = "zone_occupancy_snapshots"
    __table_args__ = (
        Index("idx_snapshot_zone_recorded", "zone_id", "recorded_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    zone_id = Column(UUID(as_uuid=True), ForeignKey("zones.id", ondelete="RESTRICT"), nullable=False, index=True)
    occupancy = Column(Integer, nullable=False)
    recorded_at = Column(DateTime(timezone=True), default=_now_utc, nullable=False, index=True)

    # Relationships
    zone = relationship("Zone", back_populates="occupancy_snapshots")


class OperationalEvent(Base):
    __tablename__ = "operational_events"
    __table_args__ = (
        Index("idx_event_zone_type_received", "zone_id", "event_type", "received_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    zone_id = Column(UUID(as_uuid=True), ForeignKey("zones.id", ondelete="RESTRICT"), nullable=True, index=True)
    source = Column(String(100), nullable=False)
    event_type = Column(String(100), nullable=False, index=True)
    payload = Column(JSONColumnType, nullable=False)
    received_at = Column(DateTime(timezone=True), default=_now_utc, nullable=False, index=True)
    correlation_id = Column(UUID(as_uuid=True), nullable=False)
    trace_id = Column(String(100), nullable=True)

    # Relationships
    zone = relationship("Zone", back_populates="operational_events")
    recommendations = relationship("Recommendation", back_populates="trigger_event")



class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = (
        Index("idx_recommendation_status_generated", "validation_status", "generated_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    trigger_event_id = Column(UUID(as_uuid=True), ForeignKey("operational_events.id", ondelete="RESTRICT"), nullable=False)
    target_role = Column(String(50), nullable=False)
    candidate_actions = Column(JSONColumnType, nullable=False)
    expected_impact = Column(JSONColumnType, nullable=False)
    validation_status = Column(String(30), default="GENERATED", nullable=False, index=True) # GENERATED, VALIDATED, APPROVED, etc.
    policy_flags = Column(ArrayColumnType, default=list, nullable=False)

    # AI Lineage
    prompt_version = Column(String(50), nullable=False)
    model_version = Column(String(50), nullable=False)
    knowledge_version = Column(String(50), nullable=False)
    confidence = Column(Float, nullable=False)
    reasoning_summary = Column(Text, nullable=False)
    reasoning_time_ms = Column(Float, nullable=True)

    # Feedback Loop
    accepted = Column(Boolean, nullable=True)
    applied = Column(Boolean, nullable=True)
    effectiveness_score = Column(Float, nullable=True)
    feedback_rating = Column(Integer, nullable=True)
    feedback_comments = Column(Text, nullable=True)

    generated_at = Column(DateTime(timezone=True), default=_now_utc, nullable=False, index=True)

    # Relationships
    trigger_event = relationship("OperationalEvent", back_populates="recommendations")
    tasks = relationship("Task", back_populates="recommendation")


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("idx_task_status_created", "status", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    recommendation_id = Column(UUID(as_uuid=True), ForeignKey("recommendations.id", ondelete="RESTRICT"), nullable=True)
    assigned_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    assigned_role = Column(String(50), nullable=False) # VOLUNTEER, SECURITY
    details = Column(Text, nullable=False)
    status = Column(String(20), default="PENDING", nullable=False, index=True) # PENDING, DISPATCHED, ACKNOWLEDGED, etc.
    created_at = Column(DateTime(timezone=True), default=_now_utc, nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc, nullable=False)

    # Relationships
    recommendation = relationship("Recommendation", back_populates="tasks")
    assigned_user = relationship("User", back_populates="tasks")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(100), nullable=True)
    ip_address = Column(String(45), nullable=True)
    details = Column(JSONColumnType, nullable=False)
    timestamp = Column(DateTime(timezone=True), default=_now_utc, nullable=False, index=True)

    # Relationships
    user = relationship("User", back_populates="audit_logs")
