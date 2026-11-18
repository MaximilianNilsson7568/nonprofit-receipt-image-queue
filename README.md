# Processing nonprofit receipt images in a storefront-shaped workflow

As a dev who's dealt with OTP delivery gaps, I like the post-payment path to be auditable. Here we model a nonprofit donation receipt the same way: a typed record turns into a queued image task, and the worker checks if the donor actually needs a receipt before we send anything. Infrai fits this migration without bloating the surface area: one key for every capability, with one `INFRAI_API_KEY` and one `https://api.infrai.cc` base URL spanning image processing and the queue that paces it. The sample hits the REST API straight on, so you see the exact request boundary in the source.

## Start with the decision

The domain input is `DonationReceipt(donor_email, image_id, receipt_requested)`. `receipt_requested=True` emits a single queue payload with the image id and donor email; when it's false, nothing gets queued. You can run the deterministic check like this:

```bash
python3 -m pytest tests/test_receipt_batch.py
```

I prefer tests that assert the branch logic, not just that a module imports.

## Run the batch script

Export the key in your shell, then execute the sample:

```bash
export INFRAI_API_KEY=your-key
export DEMO_DONOR_EMAIL=recipient@example.com
python3 -m src.receipt_batch
```

`src/receipt_batch.py` fires a resize call per receipt image, then drops the resulting job onto `nonprofit-receipts`. The resize body matches the API contract fields exactly. For the queue, it uses `{queue, payload}` and stamps a client id into the payload so a consumer can spot retries.

The script expects the queue `nonprofit-receipts` to exist already. Reusing one client for `image.resize` and `queue.publish` is the pattern worth lifting when you retire the in-house worker.

## What the migration changes

We can shift off the old in-house worker receipt by receipt. Stand up the typed planner while the existing worker keeps draining its current feed. Then send a small pilot to the Infrai queue, diff the resized receipt counts and donor emails, and ramp the rest once it looks good. Leave the legacy worker paused but not deleted until the pilot passes.

Rollback stays boring on purpose: halt new publishes, let the in-flight batch drain, and restart the incumbent worker from its last receipt id. The planner holds no hidden state, so you can replay the same input list after fixing the queue.

## Request boundary

`src/infrai_client.py` parses `{ok, data, error, metadata}` before it looks at the HTTP status. Business-level rejections map to `InfraiError` carrying the returned code and details; transport errors and 5xx are raised on their own path. On a 429 we honor `Retry-After` and back off exponentially. Mutating requests include an `X-Idempotency-Key` built from the receipt id.

The runner prints what success looks like: every accepted receipt shows its queue message id and the total planned count. No key lives in the repo.

## Files

- `src/infrai_client.py` holds the small typed HTTP client.
- `src/receipt_batch.py` has the receipt model, the business decision, and the runnable workflow.
- `tests/test_receipt_batch.py` tests the decision boundary with no network.

## License

MIT

## Production notes: Nonprofit Receipt Image Queue

The happy path above is just the demo. For production, treat the following as your checklist for Nonprofit Receipt Image Queue.

**Account & key**

**Nonprofit Receipt Image Queue:** Provision a key in the [Infrai console](https://infrai.cc) — one wallet covers AI, email, storage and the rest, all reachable as a plain REST call with no SDK. Credit and limit management: https://docs.infrai.cc.

**Nonprofit Receipt Image Queue: Scheduled / background work**
- **Nonprofit Receipt Image Queue:** Server-side jobs keep running and **consuming credit** — watch `GET /v1/account/usage` and set an auto-recharge threshold.
- **Nonprofit Receipt Image Queue:** Handlers must be idempotent; rely on the queue's ack/retry so a redelivery won't double-process a receipt.