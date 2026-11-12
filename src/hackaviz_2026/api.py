from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """A service error with a human-readable detail message."""

    detail: str


class ValidationIssue(BaseModel):
    """A serializable validation error and its location in the request."""

    type: str
    loc: list[str | int]
    msg: str


class ValidationErrorResponse(BaseModel):
    """The validation issues returned for an invalid request."""

    detail: list[ValidationIssue]
