import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from hackaviz_2026.api import ErrorResponse, ValidationErrorResponse, ValidationIssue
from hackaviz_2026.routing import ReportRequest, ReportResponse, Scenario, ScenarioId, ScenarioSummary
from routing.providers import UnimplementedReportProvider
from routing.repository import ScenarioDataError, ScenarioNotFoundError, ScenarioRepository
from routing.service import ReportNotImplementedError, RoutingService


app = FastAPI(
    title="Routing scenarios",
    responses={422: {"model": ValidationErrorResponse}},
)

DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.environ.get("ROUTING_CORS_ORIGINS", DEFAULT_CORS_ORIGINS).split(",")
        if origin.strip()
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@lru_cache(maxsize=1)
def get_routing_service() -> RoutingService:
    """Create and cache the configured scenario service."""
    default_directory = Path("data") / "output" / "scenarios"
    configured_directory = os.environ.get("ROUTING_SCENARIOS_DIR")
    if configured_directory is not None and not configured_directory.strip():
        raise ScenarioDataError("ROUTING_SCENARIOS_DIR must not be empty")
    directory = Path(configured_directory) if configured_directory is not None else default_directory
    return RoutingService(ScenarioRepository(directory), UnimplementedReportProvider())


Service = Annotated[RoutingService, Depends(get_routing_service)]


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Convert validation issues to the shared, serializable HTTP 422 format."""
    errors = [
        ValidationIssue(type=error["type"], loc=error["loc"], msg=error["msg"])
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=ValidationErrorResponse(detail=errors).model_dump(mode="json"),
    )


@app.exception_handler(ScenarioNotFoundError)
async def scenario_not_found_handler(request: Request, exc: ScenarioNotFoundError) -> JSONResponse:
    """Return HTTP 404 when a scenario is absent."""
    return JSONResponse(status_code=404, content=ErrorResponse(detail=str(exc)).model_dump())


@app.exception_handler(ScenarioDataError)
async def scenario_data_handler(request: Request, exc: ScenarioDataError) -> JSONResponse:
    """Return HTTP 503 when scenario data cannot be used."""
    return JSONResponse(status_code=503, content=ErrorResponse(detail=str(exc)).model_dump())


@app.exception_handler(ReportNotImplementedError)
async def report_not_implemented_handler(
    request: Request, exc: ReportNotImplementedError
) -> JSONResponse:
    """Return HTTP 501 while report generation is unavailable."""
    return JSONResponse(status_code=501, content=ErrorResponse(detail=str(exc)).model_dump())


@app.get(
    "/scenarios",
    response_model=list[ScenarioSummary],
    responses={503: {"model": ErrorResponse}},
)
def list_scenarios(service: Service) -> list[ScenarioSummary]:
    """List available scenario metadata."""
    return service.list_scenarios()


@app.get(
    "/scenarios/{scenario_id}",
    response_model=Scenario,
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def get_scenario(scenario_id: ScenarioId, service: Service) -> Scenario:
    """Return a scenario and its journeys."""
    return service.get_scenario(scenario_id)


@app.post(
    "/report",
    response_model=ReportResponse,
    responses={404: {"model": ErrorResponse}, 501: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def report(request: ReportRequest, service: Service) -> ReportResponse:
    """Request a report for a scenario."""
    return await service.report(request.scenario_id)
