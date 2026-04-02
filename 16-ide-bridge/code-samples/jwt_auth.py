"""JWT helpers for session ingress demos (Python 3; PyJWT).

- mint_token / verify_token: full HS256 sign+verify on a shared secret.
- decode_expiry_unverified: read `exp` from the payload without trusting it.
  Production clients use this shape to *schedule refresh* before hard expiry;
  authorization still requires verify on the server (or validated issuance path).

Never ship hardcoded secrets; the demo secret below is for local runs only.
"""

from __future__ import annotations

import time

import jwt

_DEMO_SECRET = "dev-secret-change-in-production!!"  # 32+ chars for HS256


def mint_token(
    subject: str,
    *,
    session_id: str | None = None,
    ttl_seconds: int = 60,
) -> str:
    now = int(time.time())
    claims: dict[str, str | int] = {"sub": subject, "iat": now, "exp": now + ttl_seconds}
    if session_id is not None:
        claims["session_id"] = session_id
    return jwt.encode(claims, _DEMO_SECRET, algorithm="HS256")


def verify_token(token: str) -> dict[str, str | int]:
    return jwt.decode(token, _DEMO_SECRET, algorithms=["HS256"])


def decode_expiry_unverified(token: str) -> int | None:
    """Return Unix seconds from `exp` claim without signature verification."""
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
    except jwt.exceptions.DecodeError:
        return None
    exp = payload.get("exp")
    if isinstance(exp, (int, float)):
        return int(exp)
    return None


def should_refresh_before_expiry(token: str, buffer_seconds: int = 300) -> bool:
    """True if now is within `buffer_seconds` of unverified exp (scheduling hint)."""
    exp = decode_expiry_unverified(token)
    if exp is None:
        return False
    return time.time() >= exp - buffer_seconds


if __name__ == "__main__":
    t = mint_token("user-42", session_id="sess-9", ttl_seconds=120)
    payload = verify_token(t)
    assert payload["sub"] == "user-42"
    assert payload["session_id"] == "sess-9"
    assert decode_expiry_unverified(t) == int(payload["exp"])
    long_lived = mint_token("x", ttl_seconds=86_400)
    assert not should_refresh_before_expiry(long_lived, buffer_seconds=300)
    print("jwt_auth ok")
