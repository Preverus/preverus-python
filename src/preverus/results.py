from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class ApiResult:
    data: dict[str, Any]

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.data)


@dataclass(frozen=True)
class DecisionResult:
    data: dict[str, Any]
    fallback: bool = False
    failure_reason: Optional[str] = None

    @classmethod
    def fallback_result(cls, action: str, reason: str) -> "DecisionResult":
        return cls(
            {
                "recommended_action": action,
                "risk_tier": "unknown" if action == "allow" else "review",
                "reasons": [
                    {
                        "code": "preverus_unavailable",
                        "severity": "low" if action == "allow" else "medium",
                        "message": "Preverus was unavailable; fallback policy was applied.",
                    }
                ],
            },
            fallback=True,
            failure_reason=reason,
        )

    @property
    def recommended_action(self) -> str:
        value = self.data.get("recommended_action", self.data.get("action", "review"))
        return value if isinstance(value, str) else "review"

    def is_allow(self) -> bool:
        return self.recommended_action == "allow"

    def is_review(self) -> bool:
        return self.recommended_action == "review"

    def is_block(self) -> bool:
        return self.recommended_action in {"block", "deny"}

    def to_dict(self) -> dict[str, Any]:
        return dict(self.data)


@dataclass(frozen=True)
class WebhookEvent:
    payload: dict[str, Any]
    raw_body: bytes

    @property
    def id(self) -> str:
        value = self.payload.get("id", "")
        return value if isinstance(value, str) else ""

    @property
    def type(self) -> str:
        value = self.payload.get("type", "")
        return value if isinstance(value, str) else ""

    def to_dict(self) -> dict[str, Any]:
        return dict(self.payload)
