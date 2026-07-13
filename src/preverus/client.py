from __future__ import annotations

from .http import HttpClient
from .resources import Decisions, Events, Metadata, Visitors, Webhooks


class Client:
    def __init__(
        self,
        server_key: str,
        *,
        endpoint: str = "https://api.preverus.com",
        timeout: float = 1.5,
        retries: int = 2,
        retry_delay: float = 0.15,
        max_retry_delay: float = 1.0,
    ) -> None:
        self._http = HttpClient(
            server_key=server_key,
            endpoint=endpoint,
            timeout=timeout,
            retries=retries,
            retry_delay=retry_delay,
            max_retry_delay=max_retry_delay,
        )
        self.decisions = Decisions(self._http)
        self.events = Events(self._http)
        self.visitors = Visitors(self._http)
        self.metadata = Metadata(self._http)
        self.webhooks = Webhooks()
