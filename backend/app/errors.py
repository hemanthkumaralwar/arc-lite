"""Consistent JSON error responses.

Every error body has the shape:
    {"error": "<short code>", "message": "<human-readable text>"}

Validation failures return 400, not FastAPI's default 422, because the brief requires 400
for bad input.
"""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

ERROR_CODES = {
    400: "invalid_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
}


def _validation_message(error: dict) -> str:
    loc = error.get("loc") or ()
    field = str(loc[-1]) if loc else "request body"
    if error.get("type") == "missing":
        return f"'{field}' is required."
    message = str(error.get("msg", "Invalid input."))
    return message.removeprefix("Value error, ")


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        messages = [_validation_message(err) for err in exc.errors()]
        unique = list(dict.fromkeys(messages)) or ["Invalid request."]
        return JSONResponse(
            status_code=400,
            content={"error": ERROR_CODES[400], "message": " ".join(unique)},
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException):
        code = ERROR_CODES.get(exc.status_code, "error")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": code, "message": message},
        )
