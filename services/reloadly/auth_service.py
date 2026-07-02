# ---------------------------
# Feature: Reloadly Auth Service (CONFIG CONTROLLED)
# ---------------------------

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

import requests

from config import (
    RELOADLY_AUTH_URL,
    RELOADLY_AUDIENCE,
    RELOADLY_CLIENT_ID,
    RELOADLY_CLIENT_SECRET,
    RELOADLY_ENV,
)


logger = logging.getLogger(__name__)

_reloadly_token: Optional[str] = None
_token_expiry: float = 0.0
_token_audience: str = ""


# ---------------------------
# Token cache helpers
# ---------------------------

def clear_reloadly_token() -> None:

    global _reloadly_token
    global _token_expiry
    global _token_audience

    _reloadly_token = None
    _token_expiry = 0.0
    _token_audience = ""


# ---------------------------
# Safe request
# ---------------------------

def _safe_request(
    method: str,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    json: Optional[Dict[str, Any]] = None,
    timeout: int = 15,
    retries: int = 2,
):

    last_error: Optional[Exception] = None

    for attempt in range(retries + 1):

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=json,
                timeout=timeout,
            )

            # ---------------------------
            # Return OK or business 4xx
            # ---------------------------
            if response.status_code < 500:
                return response

            logger.warning(
                "Reloadly 5xx | url=%s | status=%s | attempt=%s",
                url,
                response.status_code,
                attempt + 1,
            )

        except requests.RequestException as exc:

            last_error = exc

            logger.warning(
                "Reloadly network error | url=%s | attempt=%s | error=%s",
                url,
                attempt + 1,
                str(exc),
            )

        if attempt < retries:
            time.sleep(
                1.2 * (attempt + 1)
            )

    if last_error:
        raise RuntimeError(
            f"Reloadly request failed: {last_error}"
        )

    raise RuntimeError(
        "Reloadly request failed"
    )


# ---------------------------
# Get token
# ---------------------------

def get_reloadly_token(
    force_refresh: bool = False,
) -> str:

    global _reloadly_token
    global _token_expiry
    global _token_audience

    now = time.time()

    audience = str(
        RELOADLY_AUDIENCE or ""
    ).strip()

    client_id = str(
        RELOADLY_CLIENT_ID or ""
    ).strip()

    client_secret = str(
        RELOADLY_CLIENT_SECRET or ""
    ).strip()

    if not audience:
        raise RuntimeError(
            "Reloadly audience missing"
        )

    if not client_id or not client_secret:
        raise RuntimeError(
            "Reloadly credentials missing"
        )

    # ---------------------------
    # Use cache if valid
    # ---------------------------
    if (
        not force_refresh
        and _reloadly_token
        and now < _token_expiry
        and _token_audience == audience
    ):
        return _reloadly_token

    # ---------------------------
    # Auth payload
    # ---------------------------
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials",
        "audience": audience,
    }

    response = _safe_request(
        "POST",
        RELOADLY_AUTH_URL,
        json=payload,
        timeout=15,
        retries=2,
    )

    if response.status_code != 200:

        try:
            data = response.json()
            message = (
                data.get("message")
                or data.get("error")
                or "Reloadly auth failed"
            )

        except Exception:
            message = (
                response.text
                or "Reloadly auth failed"
            )

        logger.error(
            "Reloadly auth failed | env=%s | audience=%s | message=%s",
            RELOADLY_ENV,
            audience,
            message,
        )

        raise RuntimeError(
            message
        )

    try:
        data = response.json()

    except Exception as exc:
        raise RuntimeError(
            "Invalid Reloadly auth response"
        ) from exc

    token = data.get(
        "access_token"
    )

    if not token:
        raise RuntimeError(
            "Reloadly token missing"
        )

    expires_in = int(
        data.get(
            "expires_in",
            3600,
        )
    )

    # ---------------------------
    # Safe expiry margin
    # ---------------------------
    _reloadly_token = token
    _token_expiry = time.time() + max(
        60,
        expires_in - 60,
    )
    _token_audience = audience

    logger.info(
        "Reloadly token refreshed | env=%s | audience=%s",
        RELOADLY_ENV,
        audience,
    )

    return token