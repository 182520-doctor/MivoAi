"""Run a real two-turn conversation through the website proxy."""
import json
import os
import uuid

import httpx

base_url = os.getenv("BASE_URL", "http://127.0.0.1:3000")

with httpx.Client(base_url=base_url, timeout=180) as client:
    cid = client.post("/api/conversations").json()["id"]
    for message in (
        "请记住测试名称：青石七号。只回复已记住。",
        "刚才的测试名称是什么？只回复名称。",
    ):
        response = client.post(
            f"/api/conversations/{cid}/messages",
            json={"message": message, "clientMessageId": str(uuid.uuid4())},
        )
        response.raise_for_status()
        events = [
            json.loads(line[6:])
            for line in response.text.splitlines()
            if line.startswith("data: ")
        ]
        assert events[-1]["type"] == "done", events
        print(json.dumps(events, ensure_ascii=False))
    history = client.get(f"/api/conversations/{cid}/messages")
    history.raise_for_status()
    assert "青石七号" in history.text
    print("CONVERSATION=" + cid)
    print(history.text)
