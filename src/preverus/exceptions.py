from __future__ import annotations

from typing import Any, Optional


class PreverusError(RuntimeError):
    pass


class NetworkError(PreverusError):
    pass


class ApiError(PreverusError):
    def __init__(self, message: str, *, status_code: int = 0, error_code: str = "api_error", response: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.response = response or {}
