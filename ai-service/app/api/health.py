from fastapi import APIRouter

from app.schemas import DependencyHealth, HealthResponse, ReadinessResponse
from app.services.health_check import readiness_report


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="ai-service")


@router.get("/health/live", response_model=HealthResponse)
def liveness() -> HealthResponse:
    """Process is up (for k8s liveness probes)."""
    return HealthResponse(status="ok", service="ai-service")


@router.get("/health/ready", response_model=ReadinessResponse)
def readiness() -> ReadinessResponse:
    """Qdrant + SQLite available (for load balancers / k8s readiness)."""
    report = readiness_report(include_embed=False)
    return ReadinessResponse(
        status="ok" if report.ok else "degraded",
        service="ai-service",
        ready=report.ok,
        dependencies=[
            DependencyHealth(name=d.name, ok=d.ok, detail=d.detail)
            for d in report.dependencies
        ],
    )
