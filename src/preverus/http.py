from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any
from typing import Optional

from .exceptions import ApiError, NetworkError


class HttpClient:
    RETRYABLE_STATUSES = {408, 409, 425, 429, 500, 502, 503, 504}

    def __init__(
        self,
        *,
        server_key: str,
        endpoint: str,
        timeout: float,
        retries: int,
        retry_delay: float,
        max_retry_delay: float,
    ) -> None:
        self.server_key = server_key.strip()
        self.endpoint = endpoint.rstrip("/")
        self.timeout = timeout
        self.retries = max(0, retries)
        self.retry_delay = retry_delay
        self.max_retry_delay = max_retry_delay

    def get(self, path: str, params: Optional[dict[str, Any]] = None, headers: Optional[dict[str, str]] = None) -> dict[str, Any]:
        query = urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v not in (None, "")})
        suffix = f"?{query}" if query else ""
        return self._request("GET", f"{path}{suffix}", None, headers or {})

    def post(self, path: str, body: dict[str, Any], headers: Optional[dict[str, str]] = None) -> dict[str, Any]:
        return self._request("POST", path, body, headers or {})

    def _request(self, method: str, path: str, body: Optional[dict[str, Any]], headers: dict[str, str]) -> dict[str, Any]:
        if not self.server_key:
            raise ApiError("Missing Preverus server key.", error_code="missing_server_key")

        attempts = self.retries + 1
        for attempt in range(1, attempts + 1):
            try:
                return self._send(method, path, body, headers)
            except NetworkError:
                if attempt >= attempts:
                    raise
                self._sleep(attempt)
            except ApiError as error:
                if error.status_code not in self.RETRYABLE_STATUSES or attempt >= attempts:
                    raise
                self._sleep(attempt)

        raise NetworkError("Preverus request failed.")

    def _send(self, method: str, path: str, body: Optional[dict[str, Any]], headers: dict[str, str]) -> dict[str, Any]:
        payload = None if body is None else json.dumps(body).encode("utf-8")
        request_headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "preverus-python/0.1",
            "X-API-Key": self.server_key,
            **{k: v for k, v in headers.items() if v},
        }
        request = urllib.request.Request(
            self.endpoint + "/" + path.lstrip("/"),
            data=payload,
            headers=request_headers,
            method=method,
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as error:
            raw = error.read().decode("utf-8") if error.fp else ""
            try:
                decoded = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                decoded = {"raw": raw}
            message = decoded.get("message") if isinstance(decoded.get("message"), str) else "Preverus API error."
            code = decoded.get("code") if isinstance(decoded.get("code"), str) else "api_error"
            raise ApiError(message, status_code=error.code, error_code=code, response=decoded) from error
        except (TimeoutError, OSError, urllib.error.URLError) as error:
            raise NetworkError("Unable to connect to Preverus.") from error

    def _sleep(self, attempt: int) -> None:
        base = min(self.max_retry_delay, self.retry_delay * (2 ** max(0, attempt - 1)))
        time.sleep(base + random.uniform(0, base / 2 if base > 0 else 0))
