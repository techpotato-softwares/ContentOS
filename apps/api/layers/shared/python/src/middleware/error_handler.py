from __future__ import annotations
import json
from typing import Any

CORS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token",
    "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
    "Access-Control-Max-Age": "86400",
}

class AppError(Exception):
    def __init__(self, message: str, status_code: int = 500, code: str = "INTERNAL_ERROR"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code

class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, 404, "NOT_FOUND")

class ValidationError(AppError):
    def __init__(self, message: str = "Validation failed"):
        super().__init__(message, 400, "VALIDATION_ERROR")

class ConflictError(AppError):
    def __init__(self, message: str = "Resource already exists"):
        super().__init__(message, 409, "CONFLICT")

class ForbiddenError(AppError):
    def __init__(self, message: str = "Forbidden"):
        super().__init__(message, 403, "FORBIDDEN")

def create_success_response(data: Any, status_code: int = 200, meta: dict | None = None) -> dict:
    body: dict[str, Any] = {"success": True, "data": data}
    if meta:
        body["meta"] = meta
    return {"statusCode": status_code, "headers": {**CORS}, "body": json.dumps(body, default=str)}

def create_error_response(error: Exception) -> dict:
    if isinstance(error, AppError):
        status, code, message = error.status_code, error.code, error.message
    else:
        status, code, message = 500, "INTERNAL_ERROR", str(error) or "Internal server error"
    body: dict[str, Any] = {"success": False, "error": {"code": code, "message": message}}
    # QuotaExceededError (and similar) attach upgrade / plan / usage for billing UI
    if getattr(error, "upgrade", None) is not None:
        body["upgrade"] = bool(getattr(error, "upgrade"))
    if getattr(error, "plan", None) is not None:
        body["plan"] = getattr(error, "plan")
    if getattr(error, "usage", None) is not None:
        body["usage"] = getattr(error, "usage")
    return {"statusCode": status, "headers": {**CORS}, "body": json.dumps(body, default=str)}

def handle_options() -> dict:
    return {"statusCode": 204, "headers": {**CORS}, "body": ""}
