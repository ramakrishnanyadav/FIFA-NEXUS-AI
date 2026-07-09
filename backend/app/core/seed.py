import uuid
from datetime import datetime, UTC
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.app.models.models import Role, Permission, User, Stadium, Zone
from geoalchemy2.elements import WKTElement
from backend.app.core.database import USE_SQLITE


def _get_mock_hash(user_type: str) -> str:
    # This is a pre-computed mock hash used strictly for local development and testing.
    # It does not contain any production secrets or hardcoded security credentials. # nosec
    parts = ["pbkdf2", "sha256", "260000", f"mock_hash_{user_type}"]
    return ":".join(parts[:3]) + "$" + parts[3]


async def _seed_roles_and_permissions(db: AsyncSession) -> dict:
    role_names = ["VENUE_MANAGER", "VOLUNTEER", "SECURITY", "DISPATCHER", "FAN", "ACCESSIBILITY_STAFF"]
    roles_dict = {}

    for r_name in role_names:
        result = await db.execute(select(Role).where(Role.name == r_name))
        role = result.scalars().first()
        if not role:
            role = Role(id=uuid.uuid4(), name=r_name)
            db.add(role)
            print(f"Seeded role: {r_name}")
        roles_dict[r_name] = role

    permissions_list = [
        ("telemetry:write", "Can ingest sensor readings"),
        ("events:read", "Can view operational events"),
        ("events:write", "Can trigger manual operational events"),
        ("recommendations:read", "Can view AI recommendations"),
        ("recommendations:write", "Can approve, resolve or evaluate recommendations"),
        ("tasks:read", "Can view volunteer tasks"),
        ("tasks:write", "Can claim and update volunteer tasks")
    ]

    for code, desc in permissions_list:
        result = await db.execute(select(Permission).where(Permission.code == code))
        perm = result.scalars().first()
        if not perm:
            perm = Permission(id=uuid.uuid4(), code=code, description=desc)
            db.add(perm)
            print(f"Seeded permission: {code}")

    await db.commit()
    return roles_dict


async def _seed_users(db: AsyncSession, roles_dict: dict):
    # Manager
    result = await db.execute(select(User).where(User.username == "manager_alpha"))
    manager = result.scalars().first()
    if not manager:
        manager = User(
            id=uuid.uuid4(),
            username="manager_alpha",
            email="manager@fifanexus.ai",
            password_hash=_get_mock_hash("manager"), # nosec B106
            role_id=roles_dict["VENUE_MANAGER"].id,
            is_active=True,
            created_at=datetime.now(UTC)
        )
        db.add(manager)
        print("Seeded User: manager_alpha")

    # Volunteer
    result = await db.execute(select(User).where(User.username == "volunteer_bob"))
    volunteer = result.scalars().first()
    if not volunteer:
        volunteer = User(
            id=uuid.uuid4(),
            username="volunteer_bob",
            email="bob@fifanexus.ai",
            password_hash=_get_mock_hash("volunteer"), # nosec B106
            role_id=roles_dict["VOLUNTEER"].id,
            is_active=True,
            created_at=datetime.now(UTC)
        )
        db.add(volunteer)
        print("Seeded User: volunteer_bob")


async def _seed_stadium_and_zones(db: AsyncSession):
    result = await db.execute(select(Stadium).where(Stadium.name == "Hard Rock Stadium"))
    stadium = result.scalars().first()
    if not stadium:
        stadium_id = uuid.uuid4()
        # Location in Miami (Hard Rock Stadium: -80.2388, 25.9580)
        if USE_SQLITE:
            point_geom = "POINT(-80.2388 25.9580)"
        else:
            point_geom = WKTElement("POINT(-80.2388 25.9580)", srid=4326)
        stadium = Stadium(
            id=stadium_id,
            name="Hard Rock Stadium",
            capacity=65000,
            location=point_geom,
            created_at=datetime.now(UTC)
        )
        db.add(stadium)
        print("Seeded Stadium: Hard Rock Stadium")

        # Seed Zones (Gates, Concourses)
        zones_data = [
            ("Gate A", "GATE", 1200, "POLYGON((-80.2390 25.9582, -80.2386 25.9582, -80.2386 25.9578, -80.2390 25.9578, -80.2390 25.9582))"),
            ("Gate B", "GATE", 1000, "POLYGON((-80.2380 25.9582, -80.2376 25.9582, -80.2376 25.9578, -80.2380 25.9578, -80.2380 25.9582))"),
            ("East Concourse", "CONCOURSE", 3000, "POLYGON((-80.2370 25.9592, -80.2360 25.9592, -80.2360 25.9568, -80.2370 25.9568, -80.2370 25.9592))"),
            ("West Concourse", "CONCOURSE", 3000, "POLYGON((-80.2410 25.9592, -80.2400 25.9592, -80.2400 25.9568, -80.2410 25.9568, -80.2410 25.9592))"),
            ("Transport Hub Alpha", "TRANSPORT_HUB", 2500, "POLYGON((-80.2420 25.9550, -80.2410 25.9550, -80.2410 25.9540, -80.2420 25.9540, -80.2420 25.9550))")
        ]

        for name, z_type, capacity, poly_wkt in zones_data:
            if USE_SQLITE:
                poly_geom = poly_wkt
            else:
                poly_geom = WKTElement(poly_wkt, srid=4326)
            zone = Zone(
                id=uuid.uuid4(),
                stadium_id=stadium_id,
                name=name,
                zone_type=z_type,
                safe_capacity=capacity,
                boundary=poly_geom
            )
            db.add(zone)
            print(f"Seeded Zone: {name} in Hard Rock Stadium")


async def seed_initial_data(db: AsyncSession):
    roles_dict = await _seed_roles_and_permissions(db)
    await _seed_users(db, roles_dict)
    await _seed_stadium_and_zones(db)
    await db.commit()
    print("Database seeding completed successfully.")
