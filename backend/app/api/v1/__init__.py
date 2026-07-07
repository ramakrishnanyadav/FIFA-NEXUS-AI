from fastapi import APIRouter
from backend.app.api.v1.telemetry import router as telemetry_router
from backend.app.api.v1.events import router as events_router
from backend.app.api.v1.recommendations import router as recommendations_router
from backend.app.api.v1.tasks import router as tasks_router
from backend.app.api.v1.zones import router as zones_router
from backend.app.api.v1.assistant import router as assistant_router

router = APIRouter()

router.include_router(telemetry_router, prefix="/telemetry", tags=["Telemetry"])
router.include_router(events_router, prefix="/events", tags=["Events"])
router.include_router(recommendations_router, prefix="/recommendations", tags=["Recommendations"])
router.include_router(tasks_router, prefix="/tasks", tags=["Tasks"])
router.include_router(zones_router, prefix="/zones", tags=["Zones"])
router.include_router(assistant_router, prefix="/assistant", tags=["Assistant"])

