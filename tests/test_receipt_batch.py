from src.receipt_batch import DonationReceipt, queue_payload


def test_receipt_request_controls_queue_payload() -> None:
    requested = DonationReceipt("r-1", "donor@example.org", "img-1", True)
    declined = DonationReceipt("r-2", "donor@example.org", "img-2", False)

    assert queue_payload(requested) == {
        "receipt_id": "r-1",
        "donor_email": "donor@example.org",
        "image_id": "img-1",
    }
    assert queue_payload(declined) is None
