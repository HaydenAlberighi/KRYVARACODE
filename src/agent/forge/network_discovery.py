"""
Network Discovery module for Omega-Prime.
Provides the APIExplorer to autonomously map endpoints and infer schemas.
"""

import json
import logging
from dataclasses import asdict, dataclass
from typing import Any

import requests

logger = logging.getLogger(__name__)


@dataclass
class EndpointMap:
    url: str
    method: str
    inferred_schema: dict[str, Any]
    response_sample: Any
    status_code: int
    content_type: str


class APIExplorer:
    """
    Autonomously explores a target host to map its API surface.
    """

    def __init__(self, base_url: str, timeout: int = 5):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.discovered_endpoints: dict[str, EndpointMap] = {}

    def explore_endpoint(
        self, path: str, method: str = "GET", payload: dict[str, Any] | None = None
    ) -> EndpointMap | None:
        """
        Probes a specific endpoint and infers its schema from the response.
        """
        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            response = requests.request(method=method, url=url, json=payload, timeout=self.timeout)

            content_type = response.headers.get("Content-Type", "unknown")

            # Infer schema if response is JSON
            inferred_schema = {}
            sample_data = None

            if "application/json" in content_type:
                try:
                    sample_data = response.json()
                    inferred_schema = self._infer_json_schema(sample_data)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to decode JSON from {url}")

            endpoint_map = EndpointMap(
                url=url,
                method=method,
                inferred_schema=inferred_schema,
                response_sample=sample_data,
                status_code=response.status_code,
                content_type=content_type,
            )

            self.discovered_endpoints[path] = endpoint_map
            return endpoint_map

        except requests.RequestException as e:
            logger.error(f"Request failed for {url}: {e}")
            return None

    def _infer_json_schema(self, data: Any) -> Any:
        """
        Simple recursive type inference for JSON responses.
        """
        if isinstance(data, dict):
            return {k: self._infer_json_schema(v) for k, v in data.items()}
        elif isinstance(data, list):
            if not data:
                return ["empty_list"]
            return [self._infer_json_schema(data[0])]  # Infer from first element
        else:
            return type(data).__name__

    def get_api_map(self) -> dict[str, Any]:
        """
        Returns the full map of discovered endpoints as a dictionary.
        """
        return {path: asdict(mapping) for path, mapping in self.discovered_endpoints.items()}


# Singleton instance for the Forge to use
api_explorer = APIExplorer(base_url="http://localhost")
