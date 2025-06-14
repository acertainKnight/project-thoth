"""Gateway service for managing external API calls."""

from __future__ import annotations

import hashlib
import time
from typing import Any, Dict

import requests
from langchain_core.rate_limiters import InMemoryRateLimiter

from thoth.services.base import BaseService, ServiceError


class ExternalAPIGateway(BaseService):
    """Centralized gateway for external API requests."""

    def __init__(self, config=None):
        super().__init__(config)
        self.session = requests.Session()
        gateway_conf = self.config.api_gateway_config
        self.rate_limiter = InMemoryRateLimiter(
            requests_per_second=gateway_conf.rate_limit
        )
        self.cache_expiry = gateway_conf.cache_expiry
        self.default_timeout = gateway_conf.default_timeout
        self.endpoints: Dict[str, str] = gateway_conf.endpoints
        self._cache: dict[str, tuple[float, Any]] = {}

    def initialize(self) -> None:
        self.logger.info("External API gateway initialized")

    def _build_url(self, service: str, path: str) -> str:
        if service not in self.endpoints:
            raise ServiceError(f"Unknown service '{service}'")
        base = self.endpoints[service].rstrip("/")
        if path:
            path = path.lstrip("/")
            return f"{base}/{path}"
        return base

    def _cache_key(
        self, method: str, url: str, params: dict | None, data: Any | None
    ) -> str:
        key_str = f"{method}:{url}:{params}:{data}"
        return hashlib.sha256(key_str.encode()).hexdigest()

    def request(
        self,
        method: str,
        service: str,
        path: str = "",
        params: dict | None = None,
        data: Any | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Make a request to an external service with caching and retries."""
        try:
            url = self._build_url(service, path)
            cache_key = self._cache_key(method, url, params, data)
            cached = self._cache.get(cache_key)
            now = time.time()
            if cached and now - cached[0] < self.cache_expiry:
                return cached[1]

            last_err: Exception | None = None
            for delay in (0, 1, 3):
                if delay:
                    time.sleep(delay)
                try:
                    self.rate_limiter.acquire()
                    response = self.session.request(
                        method,
                        url,
                        params=params,
                        json=data,
                        headers=headers,
                        timeout=self.default_timeout,
                    )
                    if response.status_code == 200:
                        result = response.json()
                        self._cache[cache_key] = (now, result)
                        self.log_operation(
                            "api_request",
                            service=service,
                            url=url,
                            status=200,
                        )
                        return result
                    if response.status_code >= 500:
                        last_err = ServiceError(
                            f"Server error {response.status_code}"
                        )
                        continue
                    response.raise_for_status()
                    result = response.json()
                    self._cache[cache_key] = (now, result)
                    return result
                except requests.RequestException as e:
                    last_err = e
                    continue

            raise ServiceError(
                self.handle_error(last_err or Exception("Unknown error"), "request")
            )
        except Exception as e:
            raise ServiceError(self.handle_error(e, "request")) from e

    def get(
        self,
        service: str,
        path: str = "",
        params: dict | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Convenience method for GET requests."""
        return self.request(
            "GET", service=service, path=path, params=params, headers=headers
        )

    def post(
        self,
        service: str,
        path: str = "",
        data: Any | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Convenience method for POST requests."""
        return self.request(
            "POST", service=service, path=path, data=data, headers=headers
        )

    def clear_cache(self) -> None:
        """Clear the response cache."""
        count = len(self._cache)
        self._cache.clear()
        self.log_operation("cache_cleared", count=count)

