from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any, Callable, Optional, Union

from .http import HttpClient
from .results import ApiResult, DecisionResult, WebhookEvent


class Decisions:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def evaluate(
        self,
        input: dict[str, Any],
        *,
        visitor_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> DecisionResult:
        request_headers = dict(headers or {})
        if visitor_id:
            request_headers["X-Visitor-ID"] = visitor_id
        if idempotency_key:
            request_headers["X-Idempotency-Key"] = idempotency_key
        return DecisionResult(self._http.post("/v1/decision/evaluate", input, request_headers))


class Events:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def create(self, input: dict[str, Any], *, visitor_id: Optional[str] = None, idempotency_key: Optional[str] = None) -> ApiResult:
        headers = {}
        if visitor_id:
            headers["X-Visitor-ID"] = visitor_id
        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key
        return ApiResult(self._http.post("/v1/events", input, headers))


class Visitors:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def lookup(self, *, visitor_id: Optional[str] = None, fingerprint: Optional[str] = None, ip: Optional[str] = None) -> ApiResult:
        return ApiResult(self._http.get("/v1/score/visitors/lookup", {"visitor_id": visitor_id, "fingerprint": fingerprint, "ip": ip}))


class Metadata:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def lookup(self, key: str, value: str, *, include_global: bool = True, visitor_limit: int = 20) -> ApiResult:
        return ApiResult(
            self._http.get(
                "/v1/score/metadata/lookup",
                {"key": key, "value": value, "include_global": str(include_global).lower(), "visitor_limit": visitor_limit},
            )
        )

    def graph(self, visitor_id: str, *, limit: int = 50) -> ApiResult:
        return ApiResult(self._http.get("/v1/score/metadata/graph", {"visitor_id": visitor_id, "limit": limit}))


class Webhooks:
    def verify(self, *, raw_body: Union[bytes, str], timestamp: str, signature_header: str, secret: str, tolerance_seconds: int = 300) -> bool:
        if not timestamp.isdigit() or not signature_header or not secret:
            return False
        if abs(time.time() - int(timestamp)) > tolerance_seconds:
            return False
        body = raw_body if isinstance(raw_body, bytes) else raw_body.encode("utf-8")
        signed = timestamp.encode("utf-8") + b"." + body
        expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
        received = signature_header[3:].strip() if signature_header.startswith("v1=") else signature_header.strip()
        return hmac.compare_digest(expected, received)

    def construct_event(
        self,
        *,
        raw_body: Union[bytes, str],
        headers: dict[str, str],
        secret: str,
        tolerance_seconds: int = 300,
    ) -> WebhookEvent:
        timestamp = headers.get("X-Fraud-Webhook-Timestamp") or headers.get("x-fraud-webhook-timestamp") or ""
        signature = headers.get("X-Fraud-Webhook-Signature") or headers.get("x-fraud-webhook-signature") or ""
        if not self.verify(raw_body=raw_body, timestamp=timestamp, signature_header=signature, secret=secret, tolerance_seconds=tolerance_seconds):
            raise ValueError("Invalid Preverus webhook signature.")
        body = raw_body if isinstance(raw_body, bytes) else raw_body.encode("utf-8")
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Invalid Preverus webhook JSON payload.")
        return WebhookEvent(payload=payload, raw_body=body)

    def dispatch(self, event: WebhookEvent, handlers: dict[str, Callable[[WebhookEvent], Any]]) -> Any:
        handler = handlers.get(event.type) or handlers.get("*")
        if handler is None:
            return None
        return handler(event)
