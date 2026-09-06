"""Verify that a real Codex turn can be interrupted through the public API."""

import json
import os
import uuid

import httpx

base_url = os.getenv("BASE_URL", "http://127.0.0.1:8000")

with httpx.Client(base_url=base_url, timeout=90) as client:
    cid = client.post("/api/conversations").json()["id"]
    with client.stream(
        "POST",
        f"/api/conversations/{cid}/messages",
        json={
            "message": "请详细写一份三千字的短片创意策划。",
            "clientMessageId": str(uuid.uuid4()),
        },
    ) as response:
        for line in response.iter_lines():
            if not line.startswith("data: "):
                continue
            event = json.loads(line[6:])
            if event["type"] == "meta":
                stopped = client.post(f"/api/conversations/{cid}/interrupt")
                stopped.raise_for_status()
            if event["type"] == "done":
                assert event["status"] == "interrupted", event
                print("PASS: real turn interrupted")
                break
            assert event["type"] != "error", event
        else:
            raise AssertionError("No interrupted completion received")
