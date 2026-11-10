from pydantic import BaseModel


class ErrorResponse(BaseModel):
    detail: str


class ValidationIssue(BaseModel):
    type: str
    loc: list[str | int]
    msg: str


class ValidationErrorResponse(BaseModel):
    detail: list[ValidationIssue]
