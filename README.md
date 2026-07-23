# Preverus Python

Python client for Preverus backend enforcement.

Website: https://preverus.com  
Documentation: https://preverus.com/docs

Use this package with Django, Flask, FastAPI, or any Python backend that loads the hosted Preverus browser script on the frontend and needs trusted server-side fraud decisions.

## Install

```bash
pip install preverus
```

Requires Python 3.9+.

## Browser And Server Flow

Add the hosted script to your HTML template:

```html
<script
  src="https://api.preverus.com/v1/preverus.js"
  data-preverus-key="pk_live_xxx"
  data-preverus-auto="true"
  data-preverus-track-forms="true"
></script>

<form method="POST" action="/register" data-preverus-action="signup">
  <input name="email" type="email">
  <button type="submit">Create account</button>
</form>
```

Before submit, the script attaches:

```text
preverus_fingerprint
preverus_visitor_id
preverus_risk_session_token
preverus_browser_session_event_id
```

Your backend sends those values to Preverus with a private server key before approving sensitive actions.

## Quick Start

```python
import os
from preverus import Client

client = Client(os.environ["PREVERUS_SERVER_KEY"])

decision = client.decisions.evaluate(
    {
        "event_type": "signup",
        "user_id": "acct_42",
        "ip": request.remote_addr,
        "risk_session_token": request.form.get("preverus_risk_session_token"),
        "fingerprint": request.form.get("preverus_fingerprint"),
        "metadata": {
            "email": request.form.get("email"),
            "browser_session_event_id": request.form.get("preverus_browser_session_event_id"),
        },
    },
    visitor_id=request.form.get("preverus_visitor_id"),
    idempotency_key="signup:acct_42:request-id",
)

if decision.is_block():
    abort(403)

if decision.is_review():
    return redirect("/verify")

# Continue signup.
```

Prefer `risk_session_token` when available. It links the backend action to the browser session collected moments earlier.

## Configuration

```python
client = Client(
    os.environ["PREVERUS_SERVER_KEY"],
    endpoint="https://api.preverus.com",
    timeout=1.5,
    retries=2,
    retry_delay=0.15,
    max_retry_delay=1.0,
)
```

The client retries transient network failures and retryable statuses:

```text
408, 409, 425, 429, 500, 502, 503, 504
```

It does not retry validation or authentication errors such as `400`, `401`, `403`, or `422`.

Use idempotency keys for retried POST requests.

## Django Example

```python
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from preverus import Client

client = Client(settings.PREVERUS_SERVER_KEY)

def register(request):
    decision = client.decisions.evaluate(
        {
            "event_type": "signup",
            "user_id": request.POST.get("user_id"),
            "ip": request.META.get("REMOTE_ADDR"),
            "risk_session_token": request.POST.get("preverus_risk_session_token"),
            "fingerprint": request.POST.get("preverus_fingerprint"),
            "metadata": {
                "email": request.POST.get("email"),
                "user_agent": request.META.get("HTTP_USER_AGENT"),
            },
        },
        visitor_id=request.POST.get("preverus_visitor_id"),
    )

    if decision.is_block():
        return HttpResponseForbidden()

    if decision.is_review():
        return redirect("verify")

    # Continue registration.
```

## Flask Example

```python
from flask import abort, redirect, request
from preverus import Client

client = Client(os.environ["PREVERUS_SERVER_KEY"])

@app.post("/withdraw")
def withdraw():
    decision = client.decisions.evaluate(
        {
            "event_type": "withdraw",
            "user_id": current_user.id,
            "ip": request.remote_addr,
            "risk_session_token": request.form.get("preverus_risk_session_token"),
            "metadata": {
                "payment_address": request.form.get("payment_address"),
            },
        },
        visitor_id=request.form.get("preverus_visitor_id"),
    )

    if decision.is_block():
        abort(403)

    if decision.is_review():
        return redirect("/withdraw/review")
```

## Decisions

```python
decision.recommended_action
decision.is_allow()
decision.is_review()
decision.is_block()
decision.to_dict()
```

Recommended handling:

```text
allow  -> proceed
review -> step-up auth, hold, or manual review
block  -> deny or hard challenge
```

## Events

Use events for non-blocking fraud telemetry:

```python
event = client.events.create(
    {
        "event_type": "login",
        "user_id": "acct_42",
        "ip": "203.0.113.10",
        "fingerprint": "fp_hash",
        "metadata": {"email": "person@example.com"},
    },
    visitor_id="v_abc123",
)
```

## Lookups

```python
visitor = client.visitors.lookup(visitor_id="v_abc123")
visitor = client.visitors.lookup(fingerprint="fp_hash")

metadata = client.metadata.lookup("email", "person@example.com")
graph = client.metadata.graph("v_abc123")

user_risk_profile = client.lookup_user_risk_profile("acct_42")
```

Use lookups for investigation and context. Use `decisions.evaluate()` for final enforcement.

## Webhook Verification

```python
valid = client.webhooks.verify(
    raw_body=request.get_data(),
    timestamp=request.headers.get("X-Fraud-Webhook-Timestamp", ""),
    signature_header=request.headers.get("X-Fraud-Webhook-Signature", ""),
    secret=os.environ["PREVERUS_WEBHOOK_SECRET"],
)

if not valid:
    abort(400)
```

Webhook delivery is at-least-once. Dedupe by `X-Fraud-Webhook-Id` or payload `id`.

You can also verify, parse, and dispatch by event type:

```python
event = client.webhooks.construct_event(
    raw_body=request.get_data(),
    headers=dict(request.headers),
    secret=os.environ["PREVERUS_WEBHOOK_SECRET"],
)

if already_processed(event.id):
    return "", 204

client.webhooks.dispatch(
    event,
    {
        "decision.high_risk": lambda event: open_case(event.payload),
        "*": lambda event: log_webhook(event.type),
    },
)
```

The client verifies and parses the event, but your app should store processed event IDs in your database or cache.

## Failure Handling

The Python core client raises exceptions for API and network failures:

```python
from preverus import ApiError, NetworkError

try:
    decision = client.decisions.evaluate({...})
except ApiError as error:
    print(error.status_code, error.error_code)
except NetworkError:
    # Apply your app's fail-open, fail-review, or fail-closed policy.
```

For high-risk flows like withdrawals and payouts, a common policy is fail-review. For signup/login/checkout, many businesses prefer fail-open so the site keeps working during transient network failures.

## Production Checklist

- Keep `PREVERUS_SERVER_KEY` private.
- Use a browser key only in templates/frontend code.
- Prefer `risk_session_token` when present.
- Include `visitor_id` as `X-Visitor-ID` through the client argument.
- Send your real customer account ID as `user_id`.
- Include IP and metadata such as email, phone, username, and payment address.
- Use idempotency keys for retried POST requests.
- Treat `review` as step-up/manual review, not as automatic allow.
