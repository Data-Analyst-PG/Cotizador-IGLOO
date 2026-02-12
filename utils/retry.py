# utils/retry.py
import random
import time
from typing import Callable, TypeVar, Optional

T = TypeVar("T")

RETRIABLE_HTTP_CODES = {408, 409, 425, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524}

def _get_status_code(exc: Exception) -> Optional[int]:
    # requests.HTTPError has response; some libs wrap it differently
    resp = getattr(exc, "response", None)
    if resp is not None:
        return getattr(resp, "status_code", None)
    return getattr(exc, "status_code", None)

def retry_with_backoff(
    fn: Callable[[], T],
    *,
    tries: int = 5,
    base_delay: float = 0.6,
    max_delay: float = 8.0,
    jitter: float = 0.25,
) -> T:
    """
    Retries fn() on transient network / 5xx / Cloudflare 52x-ish issues.
    Exponential backoff + jitter.
    """
    last_exc: Exception | None = None

    for attempt in range(1, tries + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            status = _get_status_code(exc)

            # Si podemos inferir status y NO es transitorio, no reintentes
            if status is not None and status not in RETRIABLE_HTTP_CODES:
                raise

            if attempt == tries:
                break

            # backoff exponencial + jitter
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            delay = delay * (1 + random.uniform(-jitter, jitter))
            time.sleep(max(0.0, delay))

    assert last_exc is not None
    raise last_exc
