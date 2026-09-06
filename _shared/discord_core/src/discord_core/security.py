"""Ed25519 verification of incoming interaction requests.

Discord signs every HTTP interaction with the app's key pair. The message signed is
``timestamp + raw_body``. Reference:
https://docs.discord.com/developers/interactions/overview#validating-security-request-headers
"""

from __future__ import annotations

from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey

SIGNATURE_HEADER = "X-Signature-Ed25519"
TIMESTAMP_HEADER = "X-Signature-Timestamp"


def verify_signature(public_key_hex: str, signature_hex: str, timestamp: str, body: bytes) -> bool:
    """Return ``True`` when ``signature_hex`` is valid for ``timestamp + body``.

    Any malformed input (non-hex, wrong length) is treated as an invalid signature
    instead of raising, so callers can always answer HTTP 401 on ``False``.
    """
    try:
        verify_key = VerifyKey(bytes.fromhex(public_key_hex))
        verify_key.verify(timestamp.encode("utf-8") + body, bytes.fromhex(signature_hex))
    except BadSignatureError, ValueError, TypeError:
        return False
    return True


def generate_keypair() -> tuple[str, str]:
    """Generate a fresh Ed25519 key pair as ``(private_key_hex, public_key_hex)``.

    Intended for tests and smoke checks only; real apps use the Developer Portal key.
    """
    signing_key = SigningKey.generate()
    return signing_key.encode().hex(), signing_key.verify_key.encode().hex()


def sign_payload(private_key_hex: str, timestamp: str, body: bytes) -> str:
    """Sign ``timestamp + body`` and return the hex signature (mirrors what Discord sends)."""
    signing_key = SigningKey(bytes.fromhex(private_key_hex))
    return signing_key.sign(timestamp.encode("utf-8") + body).signature.hex()
