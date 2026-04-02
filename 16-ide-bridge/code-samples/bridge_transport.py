"""Newline-delimited JSON framing for IDE-style multiplexed messages.

Each line is one JSON object. Use a stable "id" on requests and echo it on
responses so async RPC and streaming notifications share one stream.

Python 3.10+ (uses dict[str, Any]).
"""

from __future__ import annotations

import json
from typing import Any


def encode_message(obj: dict[str, Any]) -> bytes:
    return (json.dumps(obj, separators=(",", ":")) + "\n").encode("utf-8")


def decode_stream(chunk: bytes) -> list[dict[str, Any]]:
    return [json.loads(line) for line in chunk.decode().splitlines() if line.strip()]


def make_request(method: str, params: dict[str, Any], req_id: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}


def make_result(req_id: str, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def make_notification(method: str, params: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "method": method, "params": params}


if __name__ == "__main__":
    rid = "req-1"
    req = make_request("ping", {}, rid)
    res = make_result(rid, {"ok": True})
    note = make_notification("stream/chunk", {"seq": 1, "text": "hello"})
    blob = encode_message(req) + encode_message(note) + encode_message(res)
    decoded = decode_stream(blob)
    assert decoded[0]["method"] == "ping"
    assert decoded[1]["method"] == "stream/chunk"
    assert decoded[2]["result"]["ok"] is True
    print("bridge_transport ok")
