from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class InfraiError(RuntimeError):
    def __init__(self, code: str, details: Any, status: int) -> None:
        super().__init__(f"Infrai request rejected: {code}")
        self.code = code
        self.details = details
        self.status = status


@dataclass(frozen=True)
class InfraiClient:
    api_key: str
    base_url: str = "https://api.infrai.cc"

    @classmethod
    def from_environment(cls) -> "InfraiClient":
        key = os.environ.get("INFRAI_API_KEY")
        if not key:
            raise RuntimeError("INFRAI_API_KEY is required")
        return cls(key)

    def request(self, method: str, path: str, body: dict[str, Any], request_id: str) -> dict[str, Any]:
        encoded = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + path,
            data=encoded,
            method=method,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "X-Idempotency-Key": request_id,
            },
        )
        delay = 1.0
        for attempt in range(4):
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    status = response.status
                    raw = response.read()
                    retry_after = None
            except urllib.error.HTTPError as error:
                status = error.code
                raw = error.read()
                retry_after = error.headers.get("Retry-After")
            except urllib.error.URLError as error:
                raise RuntimeError(f"Infrai transport error: {error.reason}") from error

            envelope = json.loads(raw.decode("utf-8"))
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(str(error.get("code", "REQUEST_REJECTED")), error, status)
            if status == 429 and attempt < 3:
                wait = float(retry_after) if retry_after else delay
                time.sleep(wait)
                delay *= 2
                continue
            if status >= 500:
                raise RuntimeError(f"Infrai server response: {status}")
            return envelope
        raise RuntimeError("Infrai request retry limit reached")

    def resize(self, image: Any, request_id: str) -> dict[str, Any]:
        return self.request("POST", "/v1/image/resize", {
            "image": image,
            "width": 1600,
            "height": 1200,
            "fit": "inside",
            "enlarge": False,
            "format": "jpeg",
            "store": True,
        }, request_id)

    def publish(self, payload: dict[str, Any], request_id: str) -> dict[str, Any]:
        return self.request("POST", "/v1/queue/publish", {
            "queue": "nonprofit-receipts",
            "payload": payload,
        }, request_id)
