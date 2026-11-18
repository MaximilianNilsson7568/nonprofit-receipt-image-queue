from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from typing import Any

from .infrai_client import InfraiClient


DEMO_RECEIPT_IMAGE = (
    {
        "base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    }
)


@dataclass(frozen=True)
class DonationReceipt:
    receipt_id: str
    donor_email: str
    image_id: str | dict[str, str]
    receipt_requested: bool


def queue_payload(receipt: DonationReceipt) -> dict[str, Any] | None:
    if not receipt.receipt_requested:
        return None
    return {
        "receipt_id": receipt.receipt_id,
        "donor_email": receipt.donor_email,
        "image_id": receipt.image_id,
    }


def process_receipts(receipts: list[DonationReceipt], client: InfraiClient) -> list[str]:
    message_ids: list[str] = []
    for receipt in receipts:
        payload = queue_payload(receipt)
        if payload is None:
            continue
        resized = client.resize(receipt.image_id, f"resize-{receipt.receipt_id}")
        data = resized.get("data") or {}
        payload["processed_image"] = str(data.get("id", receipt.image_id))
        published = client.publish(payload, f"publish-{receipt.receipt_id}")
        published_data = published.get("data") or {}
        message_ids.append(str(published_data.get("message_id", receipt.receipt_id)))
    return message_ids


def main() -> None:
    donor_email = os.environ.get("DEMO_DONOR_EMAIL")
    if not donor_email:
        raise RuntimeError("DEMO_DONOR_EMAIL is required")
    receipts = [
        DonationReceipt("donation-1001", donor_email, DEMO_RECEIPT_IMAGE, True),
        DonationReceipt("donation-1002", donor_email, DEMO_RECEIPT_IMAGE, False),
    ]
    client = InfraiClient.from_environment()
    message_ids = process_receipts(receipts, client)
    print(json.dumps({"planned": len(receipts), "queued_message_ids": message_ids}))


if __name__ == "__main__":
    main()
