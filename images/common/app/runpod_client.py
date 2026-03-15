from typing import Any

import requests

from .config import settings


class RunpodClient:
    def __init__(self) -> None:
        if not settings.runpod_api_key:
            raise RuntimeError("RUNPOD_API_KEY is required")
        if not settings.runpod_endpoint_id:
            raise RuntimeError("RUNPOD_ENDPOINT_ID is required")

        self.base_url = f"{settings.runpod_api_base_url}/{settings.runpod_endpoint_id}"
        self.headers = {
            "Authorization": f"Bearer {settings.runpod_api_key}",
            "Content-Type": "application/json",
        }

    def submit(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/run",
            headers=self.headers,
            json={"input": payload},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def get_status(self, provider_job_id: str) -> dict[str, Any]:
        response = requests.get(
            f"{self.base_url}/status/{provider_job_id}",
            headers=self.headers,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

