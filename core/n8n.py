"""Trigger the n8n workflow from the dashboard through its Webhook node."""
from __future__ import annotations

import json
import urllib.error
import urllib.request


class N8nError(Exception):
    pass


def trigger_workflow(webhook_url: str, payload: dict, timeout: int = 20) -> str:
    """POSTs to the n8n webhook. The workflow answers as soon as it starts and runs in the background."""
    req = urllib.request.Request(
        webhook_url, data=json.dumps(payload, default=str).encode(), method="POST",
        headers={"content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode(errors="ignore")[:300]
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise N8nError("n8n says the webhook isn't registered. Activate the workflow, "
                           "or use the test URL while 'Listen for test event' is on.") from e
        raise N8nError(f"n8n returned {e.code}.") from e
    except urllib.error.URLError as e:
        raise N8nError(f"Could not reach n8n: {e.reason}") from e
