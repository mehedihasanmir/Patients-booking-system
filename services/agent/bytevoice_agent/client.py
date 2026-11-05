from __future__ import annotations

import logging

import httpx

logger = logging.getLogger("bytevoice.agent")


class ApiClient:
    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.http = httpx.AsyncClient(timeout=12)

    async def post(self, path: str, payload: dict) -> dict:
        response = await self.http.post(
            f"{self.base_url}{path}",
            json=payload,
            headers={"X-Service-Token": self.token},
        )
        response.raise_for_status()
        if not response.content:
            return {}
        return response.json()

    async def aclose(self) -> None:
        await self.http.aclose()


def tool_failure(message_bn: str) -> str:
    import json

    logger.exception("tool call failed")
    return json.dumps(
        {"ok": False, "code": "backend_unavailable", "say_bn": message_bn},
        ensure_ascii=False,
    )
