import os
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
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


def get_routing_service() -> RoutingService:
    default_directory = Path("data") / "routing" / "scenarios"
    configured_directory = os.environ.get("ROUTING_SCENARIOS_DIR")
    if configured_directory is not None and not configured_directory.strip():
        raise ScenarioDataError("ROUTING_SCENARIOS_DIR must not be empty")
    directory = Path(configured_directory) if configured_directory is not None else default_directory
    return RoutingService(ScenarioRepository(directory), UnimplementedReportProvider())


Service = Annotated[RoutingService, Depends(get_routing_service)]


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
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
    return JSONResponse(status_code=404, content=ErrorResponse(detail=str(exc)).model_dump())


@app.exception_handler(ScenarioDataError)
async def scenario_data_handler(request: Request, exc: ScenarioDataError) -> JSONResponse:
    return JSONResponse(status_code=503, content=ErrorResponse(detail=str(exc)).model_dump())


@app.exception_handler(ReportNotImplementedError)
async def report_not_implemented_handler(
    request: Request, exc: ReportNotImplementedError
) -> JSONResponse:
    return JSONResponse(status_code=501, content=ErrorResponse(detail=str(exc)).model_dump())


@app.get(
    "/scenarios",
    response_model=list[ScenarioSummary],
    responses={503: {"model": ErrorResponse}},
)
def list_scenarios(service: Service) -> list[ScenarioSummary]:
    return service.list_scenarios()


@app.get(
    "/scenarios/{scenario_id}",
    response_model=Scenario,
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def get_scenario(scenario_id: ScenarioId, service: Service) -> Scenario:
    return service.get_scenario(scenario_id)


@app.post(
    "/report",
    response_model=ReportResponse,
    responses={501: {"model": ErrorResponse}},
)
async def report(request: ReportRequest, service: Service) -> ReportResponse:
    return await service.report(request.scenario)
