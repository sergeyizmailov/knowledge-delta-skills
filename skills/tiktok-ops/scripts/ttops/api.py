"""TikTok Marketing API v1.3 transport.

Stdlib only. TikTok returns HTTP 200 with a non-zero ``code`` on failure, so every
response is judged on the body, never on the HTTP status.
"""

from __future__ import annotations

import json
import os
import random
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

API_VERSION = "v1.3"
BASE_URL = "https://business-api.tiktok.com/open_api"
USER_AGENT = "ttops/1.0 (+tiktok-ops skill)"

# Codes that mean "throttled". TikTok signals these in the JSON body with HTTP 200.
RATE_LIMIT_CODES = {40016, 40100, 40132, 40133}
# 40100 is the developer-app QPM/QPD breach. TikTok documents the QPM recovery as a
# flat five-minute wait, so retrying sooner re-enters the penalty window.
QPM_PENALTY_SECONDS_CODE = 40100
QPM_PENALTY_SECONDS = 300.0
# HTTP statuses that mean "back off" regardless of what the body says. TikTok is not
# documented to send these; infrastructure in front of it can.
RETRYABLE_HTTP_STATUS = {429, 500, 502, 503, 504}
# Codes where an immediate retry is legitimate (documented as transient).
TRANSIENT_CODES = {40202, 40902, 40903, 40913, 50000}
# Codes that mean the token is dead. Never retry; escalate.
AUTH_DEAD_CODES = {40102, 40104, 40105, 40106}

WRITE_PATHS = (
    "/create/", "/update/", "/delete/", "/upload/", "/assign/", "/unassign/",
    "/transfer/", "/invite/", "/add/", "/bind/", "/unbind/", "/apply/",
    "/authorize/", "/confirm/", "/cancel/", "/save/", "/promote/", "/appeal/",
)


class TikTokError(Exception):
    """A non-zero ``code`` in a TikTok API response body."""

    def __init__(self, code, message, request_id=None, path=None, payload=None):
        self.code = code
        self.message = message
        self.request_id = request_id
        self.path = path
        self.payload = payload
        super().__init__(f"[{code}] {message} (path={path} request_id={request_id})")

    def as_dict(self):
        return {
            "code": self.code,
            "message": self.message,
            "request_id": self.request_id,
            "path": self.path,
        }


class PartialSuccessError(TikTokError):
    """``code: 20001`` — some items in a batch failed.

    Never a success. TikTok returns the successful items in ``data`` and reports
    the failures per item, so a caller that wants to salvage the good half can
    catch this and read ``payload``. The default is to stop, because silently
    continuing loses half a launch.
    """


class TransportError(Exception):
    """Network/HTTP failure with no usable TikTok response body."""


def is_write(path: str) -> bool:
    return any(seg in path for seg in WRITE_PATHS)


class Client:
    """Thin, deliberately boring API client.

    ``allow_writes`` is the transport guard: a client built for a read-only phase
    physically cannot POST to a write endpoint, so a bug in calling code fails
    loudly instead of spending money.
    """

    def __init__(self, token=None, *, allow_writes=False, timeout=60,
                 max_retries=4, base_url=BASE_URL, sleep=time.sleep, dry_run=False):
        self.token = token or os.environ.get("TIKTOK_ACCESS_TOKEN") or ""
        self.allow_writes = allow_writes
        self.timeout = timeout
        self.max_retries = max_retries
        self.base_url = base_url.rstrip("/")
        self._sleep = sleep
        self.dry_run = dry_run
        self.calls = []  # (method, path, code) — audit trail for verify/report

    # -- internals ---------------------------------------------------------

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{API_VERSION}{path}"

    def _headers(self):
        if not self.token:
            raise TransportError(
                "No access token. Set TIKTOK_ACCESS_TOKEN in the environment; "
                "never pass a token on the command line."
            )
        return {
            "Access-Token": self.token,
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        }

    def _backoff(self, attempt: int, rate_limited: bool, code=None) -> float:
        """Seconds to wait before the next attempt.

        TikTok documents QPM recovery as **wait 5 minutes**, so a 20-second first
        retry on a 40100 is not backing off — it is re-offending inside the penalty
        window, which can extend it. Per-app QPM breaches therefore start at the full
        documented wait. Per-advertiser (40133) and per-endpoint (40016) throttles are
        about serializing, not about a fixed penalty, so they ramp.
        """
        if code == QPM_PENALTY_SECONDS_CODE:
            return QPM_PENALTY_SECONDS + random.uniform(0, 15.0)
        base = 20.0 if rate_limited else 1.0
        return min(base * (2 ** attempt) + random.uniform(0, base / 2), 300.0)

    def _request(self, method, path, params=None, body=None):
        url = self._url(path)
        data = None
        if method == "GET" and params:
            url = f"{url}?{urllib.parse.urlencode(_flatten(params))}"
        if method == "POST":
            data = json.dumps(body or {}).encode("utf-8")

        req = urllib.request.Request(url, data=data, headers=self._headers(), method=method)
        ctx = ssl.create_default_context()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=ctx) as resp:
                raw = resp.read().decode("utf-8")
                status = resp.status
        except urllib.error.HTTPError as exc:  # TikTok sometimes does use real statuses
            raw = exc.read().decode("utf-8", "replace")
            status = exc.code
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise TransportError(f"{type(exc).__name__}: {exc}") from exc

        try:
            return json.loads(raw), status
        except json.JSONDecodeError as exc:
            raise TransportError(f"non-JSON response (HTTP {status}): {raw[:400]}") from exc

    # -- public ------------------------------------------------------------

    def call(self, method, path, params=None, body=None):
        """Make one API call and return ``data``. Raises TikTokError on code != 0."""
        method = method.upper()
        if method == "POST" and is_write(path) and not self.allow_writes:
            raise TransportError(
                f"Refusing to POST to write endpoint {path}: this client is read-only. "
                "Write access is granted only by a command that has passed its gates."
            )
        if self.dry_run and method == "POST" and is_write(path):
            self.calls.append((method, path, "DRY_RUN"))
            return {"_dry_run": True, "_path": path, "_body": body}

        last = None
        for attempt in range(self.max_retries + 1):
            try:
                payload, status = self._request(method, path, params, body)
            except TransportError as exc:
                last = exc
                # A dropped connection on a write may still have applied. Never
                # auto-retry a write; the caller reconciles from state.
                if method == "POST" and is_write(path):
                    raise TransportError(
                        f"{exc} — write outcome UNKNOWN for {path}. Do not retry blindly; "
                        "reconcile against the account before re-running."
                    ) from exc
                if attempt == self.max_retries:
                    raise
                self._sleep(self._backoff(attempt, False))
                continue

            code = payload.get("code")
            self.calls.append((method, path, code))

            # TikTok signals throttling in the body, but "TikTok does not send 429" is a
            # claim about its documented behaviour, not a guarantee about every proxy,
            # gateway and CDN between here and there. If a real 429 or 5xx arrives, treat
            # it as throttling rather than letting a code:0-shaped body sail through or a
            # missing code fall to an unhelpful error.
            if status in RETRYABLE_HTTP_STATUS and code != 0:
                if attempt == self.max_retries:
                    raise TikTokError(code or status,
                                      payload.get("message", "") or f"HTTP {status}",
                                      payload.get("request_id"), path, payload)
                self._sleep(self._backoff(attempt, True, code))
                continue

            if code == 0:
                return payload.get("data", {})

            if code == 20001:
                raise PartialSuccessError(
                    code,
                    (payload.get("message", "") or "partial success") +
                    " — some items in this batch failed. Inspect the per-item results in "
                    "the payload; do not treat this as a completed operation.",
                    payload.get("request_id"), path, payload,
                )

            err = TikTokError(code, payload.get("message", ""), payload.get("request_id"), path, payload)
            if code in AUTH_DEAD_CODES:
                raise err
            if code in RATE_LIMIT_CODES or code in TRANSIENT_CODES:
                if attempt == self.max_retries:
                    raise err
                self._sleep(self._backoff(attempt, code in RATE_LIMIT_CODES, code))
                last = err
                continue
            raise err
        if isinstance(last, Exception):
            raise last
        raise TransportError("exhausted retries with no error recorded")

    def get(self, path, params=None):
        return self.call("GET", path, params=params)

    def post(self, path, body=None):
        return self.call("POST", path, body=body)

    def paged(self, path, params=None, page_size=100, max_pages=200):
        """Iterate a list endpoint. TikTok paginates via page/page_size + page_info."""
        params = dict(params or {})
        page = 1
        while page <= max_pages:
            params["page"] = page
            params["page_size"] = page_size
            data = self.get(path, params)
            for row in data.get("list", []):
                yield row
            info = data.get("page_info") or {}
            if page >= int(info.get("total_page") or 0):
                return
            page += 1


def _flatten(params):
    """TikTok GET expects JSON-encoded values for list/dict params."""
    out = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple, dict, bool)):
            out[key] = json.dumps(value)
        else:
            out[key] = value
    return out
