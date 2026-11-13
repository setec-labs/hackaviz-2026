import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from hackaviz_2026.api import ErrorResponse, ValidationErrorResponse, ValidationIssue
from hackaviz_2026.journey_safety import JourneySafetyRequest, JourneySafetyResponse
from hackaviz_2026.models import (
    EvaluateRequest,
    EvaluateResponse,
    Indicator,
    SafetyIndexRequest,
    SafetyIndexResponse,
    ScoreRequest,
    ScoreResponse,
)
from safety.lighting import DEFAULT_LIGHTING_RASTER, LightingIndicatorProvider
from safety.population_density import (
    DEFAULT_POPULATION_DENSITY_RASTER,
    PopulationDensityIndicatorProvider,
)
from safety.providers import IndicatorDataError, IndicatorUnavailableError
from safety.ridership import DEFAULT_RIDERSHIP_CSV, RidershipIndicatorProvider
from safety.service import IndicatorNotImplementedError, IndicatorService, UnknownIndicatorError


DEFAULT_CORS_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")


def _read_path_setting(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    if value is None:
        return default
    if not value.strip():
        raise IndicatorDataError(f"{name} must not be empty")
    return Path(value)


def _cors_origins() -> list[str]:
    value = os.environ.get("SAFETY_CORS_ORIGINS")
    if value is None:
        return list(DEFAULT_CORS_ORIGINS)
    return [origin.strip() for origin in value.split(",") if origin.strip()]


app = FastAPI(
    title="Safety indicators",
    responses={422: {"model": ValidationErrorResponse}},
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@lru_cache(maxsize=1)
def get_indicator_service() -> IndicatorService:
    """Create and cache the position and contextual providers."""
    raster_path = _read_path_setting("SAFETY_LIGHTING_RASTER", DEFAULT_LIGHTING_RASTER)
    ridership_path = _read_path_setting("SAFETY_RIDERSHIP_CSV", DEFAULT_RIDERSHIP_CSV)
    density_path = _read_path_setting(
        "SAFETY_POPULATION_DENSITY_RASTER", DEFAULT_POPULATION_DENSITY_RASTER,
    )
    return IndicatorService(
        (LightingIndicatorProvider(raster_path), PopulationDensityIndicatorProvider(density_path)),
        RidershipIndicatorProvider(ridership_path),
    )


Service = Annotated[IndicatorService, Depends(get_indicator_service)]


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


@app.exception_handler(IndicatorNotImplementedError)
async def indicator_not_implemented_handler(
    request: Request, exc: IndicatorNotImplementedError
) -> JSONResponse:
    """Return HTTP 501 when an indicator is not implemented."""
    return JSONResponse(status_code=501, content=ErrorResponse(detail=str(exc)).model_dump())


@app.exception_handler(UnknownIndicatorError)
async def unknown_indicator_handler(request: Request, exc: UnknownIndicatorError) -> JSONResponse:
    """Return HTTP 400 for an unknown indicator ID."""
    return JSONResponse(status_code=400, content=ErrorResponse(detail=str(exc)).model_dump())


@app.exception_handler(IndicatorUnavailableError)
async def indicator_unavailable_handler(
    request: Request, exc: IndicatorUnavailableError
) -> JSONResponse:
    """Return HTTP 404 when no data covers a position."""
    return JSONResponse(status_code=404, content=ErrorResponse(detail=str(exc)).model_dump())


@app.exception_handler(IndicatorDataError)
async def indicator_data_handler(request: Request, exc: IndicatorDataError) -> JSONResponse:
    """Return HTTP 503 when an indicator's source data cannot be used."""
    return JSONResponse(status_code=503, content=ErrorResponse(detail=str(exc)).model_dump())


@app.get("/indicators", response_model=list[Indicator])
async def list_indicators(service: Service) -> list[Indicator]:
    """List the available indicator metadata."""
    return service.list_indicators()


@app.post(
    "/evaluate",
    response_model=EvaluateResponse,
    responses={
        404: {"model": ErrorResponse},
        501: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
async def evaluate(request: EvaluateRequest, service: Service) -> EvaluateResponse:
    """Evaluate every indicator at the requested position."""
    return await service.evaluate(request.position)


@app.post(
    "/score",
    response_model=ScoreResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        501: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
async def score(request: ScoreRequest, service: Service) -> ScoreResponse:
    """Calculate a normalized weighted indicator score."""
    return await service.score(request)


@app.post(
    "/safety-index",
    response_model=SafetyIndexResponse,
    responses={501: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def safety_index(request: SafetyIndexRequest, service: Service) -> SafetyIndexResponse:
    """Calculate one equal-weight index per requested position."""
    return await service.safety_index(request.points)


@app.post(
    "/journey-safety",
    response_model=JourneySafetyResponse,
    responses={501: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def journey_safety(request: JourneySafetyRequest, service: Service) -> JourneySafetyResponse:
    """Evaluate local contexts and a configurable weighted global score per journey."""
    return await service.journey_safety(request)
