import json
import time
from typing import Any

import pytest

from discord_core.security import generate_keypair, sign_payload


@pytest.fixture(scope="session")
def keypair() -> tuple[str, str]:
    return generate_keypair()


@pytest.fixture
def signer(keypair: tuple[str, str]):
    private_key, _ = keypair

    def _sign(payload: dict[str, Any]) -> tuple[bytes, dict[str, str]]:
        body = json.dumps(payload).encode()
        timestamp = str(int(time.time()))
        headers = {
            "Content-Type": "application/json",
            "X-Signature-Ed25519": sign_payload(private_key, timestamp, body),
            "X-Signature-Timestamp": timestamp,
        }
        return body, headers

    return _sign


def _command_interaction(
    name: str, options: list[dict[str, Any]] | None = None, **extra: Any
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": "1001",
        "application_id": "2002",
        "type": 2,
        "token": "tok",
        "version": 1,
        "guild_id": "3003",
        "channel_id": "4004",
        "locale": "en-US",
        "member": {"user": {"id": "5005", "username": "tester"}, "roles": []},
        "data": {"id": "6006", "name": name, "type": 1, "options": options or []},
    }
    payload.update(extra)
    return payload


def _component_interaction(custom_id: str, values: list[str] | None = None) -> dict[str, Any]:
    return {
        "id": "1001",
        "application_id": "2002",
        "type": 3,
        "token": "tok",
        "version": 1,
        "guild_id": "3003",
        "member": {"user": {"id": "5005", "username": "tester"}, "roles": []},
        "message": {"id": "7007", "content": ""},
        "data": {"custom_id": custom_id, "component_type": 2, "values": values or []},
    }


@pytest.fixture
def command_interaction():
    return _command_interaction


@pytest.fixture
def component_interaction():
    return _component_interaction
