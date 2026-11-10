from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from hackaviz_2026.api import ErrorResponse, ValidationErrorResponse, ValidationIssue
from hackaviz_2026.models import (
    EvaluateRequest,
    EvaluateResponse,
    Indicator,
    ScoreRequest,
    ScoreResponse,
)
from safety.providers import LightingIndicatorProvider
from safety.service import IndicatorNotImplementedError, IndicatorService, UnknownIndicatorError


app = FastAPI(
    title="Safety indicators",
    responses={422: {"model": ValidationErrorResponse}},
)


def get_indicator_service() -> IndicatorService:
    return IndicatorService((LightingIndicatorProvider(),))


Service = Annotated[IndicatorService, Depends(get_indicator_service)]


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


@app.exception_handler(IndicatorNotImplementedError)
async def indicator_not_implemented_handler(
    request: Request, exc: IndicatorNotImplementedError
) -> JSONResponse:
    return JSONResponse(status_code=501, content=ErrorResponse(detail=str(exc)).model_dump())


@app.exception_handler(UnknownIndicatorError)
async def unknown_indicator_handler(request: Request, exc: UnknownIndicatorError) -> JSONResponse:
    return JSONResponse(status_code=400, content=ErrorResponse(detail=str(exc)).model_dump())


@app.get("/indicators", response_model=list[Indicator])
async def list_indicators(service: Service) -> list[Indicator]:
    return service.list_indicators()


@app.post(
    "/evaluate",
    response_model=EvaluateResponse,
    responses={501: {"model": ErrorResponse}},
)
async def evaluate(request: EvaluateRequest, service: Service) -> EvaluateResponse:
    return await service.evaluate(request.position)


@app.post(
    "/score",
    response_model=ScoreResponse,
    responses={400: {"model": ErrorResponse}, 501: {"model": ErrorResponse}},
)
async def score(request: ScoreRequest, service: Service) -> ScoreResponse:
    return await service.score(request)
