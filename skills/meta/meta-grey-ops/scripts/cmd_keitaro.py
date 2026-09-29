#!/usr/bin/env python3
"""Facebook -> Keitaro daily cost push and per-ad join for `metaops` (tracker-ops/01).

    metaops [--profile P] keitaro push   [--days N | --since D --until D] [--keitaro-campaign ID]
                                         [--keitaro-currency CUR] [--readback-wait S] [--confirm PUSH]
    metaops [--profile P] keitaro report [--days N | --since D --until D] [--keitaro-campaign ID]
                                         [--by ad|adset|day]

`--profile` also works after the subcommand. Both commands are workspace-bound: the ad account
comes from the active profile, never from a flag. The Keitaro campaign comes from
`--keitaro-campaign` or the optional profile field `keitaro_campaign_id`; every Keitaro call
carries that campaign (`campaign_ids` on the push, a `campaign_id` filter on every read).

push
    Without `--confirm PUSH` it is a dry run: it reads Facebook (account tz/currency, ad-level
    daily insights over ALL effective statuses, an account-level total for the same days), reads
    Keitaro (campaign cost model, cost/clicks it stores now) and prints the exact
    `POST /admin_api/v1/clicks/update_costs` entries. Nothing is written to Keitaro. With
    `--confirm PUSH` it sends one call per day (<= 100 entries per call), then reads the cost back
    (`/report/build`, grouped by day and `sub_id_6`) and prints FB spend vs Keitaro cost per day.

    One entry per (ad, day): `filters: {sub_id_6: "<ad_id>"}`, the ad account's timezone and
    currency as-is (Keitaro converts at its own rate). Re-pushing a day overwrites it, so the
    trailing days are re-pushed on every run. Names are never used as keys.

    Spend that the ad rows do not explain (account total minus sum of ad rows) is reported as
    `unattributed`. It is NOT pushed: an entry keyed on `ad_campaign_id` matches the same clicks as
    the per-ad entries of that campaign and would overwrite them. The only non-overlapping case, a
    campaign with no ad row at all on that day, is listed as a `remainder_candidates` entry for a
    human to decide.

report
    Joins FB spend per ad (insights) with Keitaro per `sub_id_6`: clicks, leads, sales, cost,
    sale_revenue. regs = leads + sales, deps = sales, cost/reg, cost/dep, ROI on sale_revenue. The
    `conversions` metric is never requested. lead_revenue is printed as a sanity check (must be 0).
    Rows whose sub id still holds a `{{...}}` macro, or is empty, are excluded and counted apart.

Credentials (environment only, never argv): KEITARO_URL (base, e.g. https://host) and
KEITARO_API_KEY (sent in the `Api-Key` header). Optional KEITARO_CURRENCY = Keitaro's base
currency (see --keitaro-currency). Missing variables give a JSON envelope naming them.

Transport (urllib, direct, ambient proxy variables ignored): 20 s timeout per call; redirects are
refused (the header would follow them); no retry on 4xx/5xx or timeouts; ONE retry after a
connection reset before any response, which is safe for the push because re-sending an
update_costs overwrite yields the same state. Facebook calls go through graph.py unchanged
(throttle = cooldown, never a retry).

register(sub, ctx) wires this onto the shared subparsers; ctx is the metaops module itself.
"""

from __future__ import annotations

import argparse
import datetime as dt
import http.client
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

RESULT_COMMAND = "keitaro"
PUSH_SCHEMA = "metaops.keitaro-push/v1"

KEITARO_TIMEOUT = 20            # seconds, every call
DEFAULT_DAYS = 3                # trailing, includes today
MAX_DAYS = 31
ENTRY_CHUNK = 100               # update_costs entries per call
DELTA_FLAG_PCT = 3.0            # readback tolerance and the "delta" flag
READBACK_WAIT_DEFAULT = 45      # seconds of polling after a push (lag is real, this is bounded)
READBACK_POLL = 15
PAGE_LIMIT = 500                # Graph insights page size
KT_PAGE_LIMIT = 1000            # report/build rows per page
MAX_PAGES = 200
LIST_CAP = 200                  # per-list cap inside the JSON payload

# Keitaro request vocabulary. UNVERIFIED against a live instance (see references/01-keitaro.md):
# the date format for update_costs, the EQUALS operator, `limit`/`offset` on report/build.
KT_DATE_START = "{day} 00:00"
KT_DATE_END = "{day} 23:59"
KT_EQ_OPERATOR = "EQUALS"
KT_AD_DIMENSION = "sub_id_6"    # the operator's Keitaro campaign: FB ad id (tracker-ops/01)
KT_MEASURES_JOIN = ("clicks", "leads", "sales", "cost", "sale_revenue", "lead_revenue")
KT_MEASURES_COST = ("clicks", "cost")

# Ad.effective_status enum (meta-ads v26 reference, same list the launcher tests pin). DELETED and
# ARCHIVED matter most: insights on the account edge leave those ads out unless they are asked for.
# ADSET_DELETED / CAMPAIGN_DELETED (seen in verify.py) are not in the documented enum and would risk
# a code-100 on the whole call; the account-total check below exposes any gap they leave.
INSIGHT_EFFECTIVE_STATUSES = (
    "ACTIVE", "PAUSED", "DELETED", "PENDING_REVIEW", "DISAPPROVED", "PREAPPROVED",
    "PENDING_BILLING_INFO", "CAMPAIGN_PAUSED", "ARCHIVED", "ADSET_PAUSED", "IN_PROCESS",
    "WITH_ISSUES",
)
CAMPAIGN_EFFECTIVE_STATUSES = ("ACTIVE", "PAUSED", "DELETED", "ARCHIVED", "IN_PROCESS", "WITH_ISSUES")
AD_FIELDS_PUSH = "ad_id,ad_name,campaign_id,adset_id,spend,impressions,inline_link_clicks,date_start,date_stop"
AD_FIELDS_REPORT = AD_FIELDS_PUSH + ",adset_name"

USER_AGENT = "metaops-keitaro/1"  # urllib's default UA is blocked by Cloudflare-fronted trackers
LOOPBACK = ("localhost", "127.0.0.1", "::1")

_sleep = time.sleep


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


# --------------------------------------------------------------------------- small helpers


def _say(text: str = "") -> None:
    """Human-readable diagnostics go to stderr, like every peer: stdout stays one JSON envelope."""
    print(text, file=sys.stderr)


def _dec(value: Any, label: str | None = None) -> Decimal:
    """Decimal from a Graph/Keitaro scalar. With `label`, garbage is an error; without, zero."""
    if value is None or value == "":
        return Decimal(0)
    try:
        out = Decimal(str(value))
    except InvalidOperation:
        out = Decimal("NaN")
    if not out.is_finite():
        if label:
            raise ValueError(f"{label}: not a number: {value!r}")
        return Decimal(0)
    return out


def _r2(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _table(header: list[str], rows: list[list[str]], left: int = 1, last_left: bool = True) -> str:
    """Aligned plain-text table: the first `left` columns and (by default) the last one are
    left-aligned, the others right-aligned."""
    widths = [max([len(header[i])] + [len(r[i]) for r in rows]) for i in range(len(header))]
    ncols = len(header)

    def line(cells: list[str]) -> str:
        return "  ".join(
            c.ljust(widths[i]) if i < left or (last_left and i == ncols - 1) else c.rjust(widths[i])
            for i, c in enumerate(cells)
        ).rstrip()

    return "\n".join([line(header), *(line(r) for r in rows)])


def _warn(warnings: list[dict[str, str]], code: str, message: str) -> None:
    warnings.append({"code": code, "message": message})
    _say(f"  ! {message}")


def _stamp(ctx) -> str:
    return ctx.now_utc().replace(":", "").replace("+", "_")


def _daterange(since: dt.date, until: dt.date) -> list[str]:
    return [(since + dt.timedelta(days=i)).isoformat() for i in range((until - since).days + 1)]


def _capped(items: list[Any]) -> list[Any]:
    return items[:LIST_CAP]


# --------------------------------------------------------------------------- Keitaro transport


class KeitaroError(Exception):
    """A Keitaro call that did not produce a usable answer. `outcome_unknown` is true when a WRITE
    may have been applied (timeout, reset after the retry, 5xx): read the cost back, don't guess."""

    def __init__(self, message: str, *, status: int = 0, path: str = "", kind: str = "http",
                 outcome_unknown: bool = False):
        super().__init__(message)
        self.message = message
        self.status = status
        self.path = path
        self.kind = kind
        self.outcome_unknown = outcome_unknown

    def as_dict(self) -> dict[str, Any]:
        return {"kind": "keitaro", "message": self.message, "status": self.status,
                "path": self.path, "reason": self.kind, "outcome_unknown": self.outcome_unknown}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect would replay the Api-Key header (and a POST body) at whatever host answers."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


def _api_base(raw: str) -> str:
    """`https://host` (or with an /admin_api/v1 suffix, or a subdirectory install) -> API base."""
    parts = urllib.parse.urlsplit(raw.strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise KeitaroError("KEITARO_URL must be an absolute http(s) URL such as https://host",
                           kind="config")
    if parts.scheme == "http" and parts.hostname not in LOOPBACK:
        raise KeitaroError("KEITARO_URL must be https: the API key travels in a header", kind="config")
    if parts.username or parts.password or parts.query or parts.fragment:
        raise KeitaroError("KEITARO_URL must be a plain base URL (no credentials, query or fragment)",
                           kind="config")
    path = parts.path.rstrip("/")
    if not path.endswith("/admin_api/v1"):
        path += "/admin_api/v1"
    return f"{parts.scheme}://{parts.netloc}{path}"


def _is_reset(reason: Any) -> bool:
    # RemoteDisconnected subclasses ConnectionResetError: the server closed without answering.
    return isinstance(reason, (ConnectionResetError, BrokenPipeError))


class KeitaroClient:
    def __init__(self, base_url: str, api_key: str, *, timeout: int = KEITARO_TIMEOUT,
                 opener: Any = None, redact: Any = None):
        self.base = _api_base(base_url)
        self._key = api_key
        self.timeout = timeout
        self._redact_fn = redact
        self._opener = opener or urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _NoRedirect())

    def redact(self, text: Any) -> str:
        out = str(text)
        if self._key:
            out = out.replace(self._key, "<KEITARO_API_KEY>")
        return self._redact_fn(out) if self._redact_fn else out

    def get(self, path: str) -> Any:
        return self.request("GET", path)

    def post(self, path: str, body: dict[str, Any], *, write: bool = False) -> Any:
        return self.request("POST", path, body, write=write)

    def request(self, method: str, path: str, body: Any = None, *, write: bool = False) -> Any:
        """One call. Errors carry the path, never the URL: the key is a header, and the message is
        redacted anyway. `write` marks calls whose outcome is unknown after a lost answer."""
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        headers = {"Api-Key": self._key, "Accept": "application/json", "User-Agent": USER_AGENT}
        if data is not None:
            headers["Content-Type"] = "application/json"
        retried = False
        while True:
            req = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
            try:
                resp = self._opener.open(req, timeout=self.timeout)
                break
            except urllib.error.HTTPError as exc:
                raise self._http_error(exc, path, write) from None
            except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
                reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
                if _is_reset(reason) and not retried:
                    # Reset before any response: nothing came back, an overwrite is repeatable.
                    retried = True
                    _sleep(1.0)
                    continue
                raise self._transport_error(reason, path, write, retried) from None
        try:
            with resp:
                raw = resp.read()
        except (OSError, http.client.HTTPException) as exc:
            raise KeitaroError(
                f"{method} {path}: connection lost while reading the answer "
                f"({self.redact(type(exc).__name__)})",
                path=path, kind="transport", outcome_unknown=write) from None
        return self._decode(raw, method, path)

    def _http_error(self, exc: urllib.error.HTTPError, path: str, write: bool) -> KeitaroError:
        try:
            text = exc.read(4096).decode("utf-8", errors="replace")
        except (OSError, http.client.HTTPException):
            text = ""
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                text = str(parsed.get("message") or parsed.get("error") or text)
        except ValueError:
            pass
        text = self.redact(text.strip())[:500]
        hint = " (redirect refused: check KEITARO_URL scheme/host)" if 300 <= exc.code < 400 else ""
        return KeitaroError(
            f"HTTP {exc.code} on {path}: {text or exc.reason}{hint}",
            status=exc.code, path=path, kind="http",
            outcome_unknown=bool(write and exc.code >= 500))

    def _transport_error(self, reason: Any, path: str, write: bool, retried: bool) -> KeitaroError:
        if isinstance(reason, TimeoutError) or "timed out" in str(reason).lower():
            what = f"no answer within {self.timeout} s"
            kind = "timeout"
        else:
            what = self.redact(f"{type(reason).__name__}: {reason}")[:200]
            kind = "transport"
        extra = " (retried once after a reset)" if retried else ""
        return KeitaroError(f"{path}: {what}{extra}", path=path, kind=kind, outcome_unknown=write)

    def _decode(self, raw: bytes, method: str, path: str) -> Any:
        text = raw.decode("utf-8", errors="replace").strip()
        if not text:
            return {}
        try:
            return json.loads(text)
        except ValueError:
            raise KeitaroError(
                f"{method} {path}: answer is not JSON: {self.redact(text)[:200]}",
                path=path, kind="non_json") from None


def _make_client(ctx) -> KeitaroClient:
    url = os.environ.get("KEITARO_URL", "").strip()
    key = os.environ.get("KEITARO_API_KEY", "").strip()
    missing = [name for name, value in (("KEITARO_URL", url), ("KEITARO_API_KEY", key)) if not value]
    if missing:
        raise KeitaroError(
            f"{' and '.join(missing)} {'is' if len(missing) == 1 else 'are'} not set; export "
            "KEITARO_URL (base, e.g. https://host) and KEITARO_API_KEY in the environment "
            "(never on argv)",
            kind="credentials")
    ctx.graph.register_secret(key)  # graph.redact then masks it in every output path of metaops
    return KeitaroClient(url, key, redact=ctx.graph.redact)


# --------------------------------------------------------------------------- arguments and range


def _profile(ctx, args, label: str):
    workspace = getattr(args, "workspace_obj", None)
    if not workspace:
        raise ctx.MetaOpsError(f"{label} requires a workspace; run inside a workspace or pass --workspace")
    name, profile = workspace.profile(getattr(args, "profile", None))
    return workspace, name, profile


def _campaign_id(args, name: str, profile: dict[str, Any], ctx) -> tuple[int, str]:
    flag = getattr(args, "keitaro_campaign", None)
    if flag:
        raw, source = str(flag).strip(), "flag"
    elif profile.get("keitaro_campaign_id"):
        raw, source = str(profile["keitaro_campaign_id"]).strip(), "profile"
    else:
        raise ctx.MetaOpsError(
            "Keitaro campaign id required: pass --keitaro-campaign ID or set "
            f"profiles.{name}.keitaro_campaign_id in workspace.json")
    if not raw.isdigit():
        raise ctx.MetaOpsError(f"Keitaro campaign id must be numeric, got {raw!r}")
    return int(raw), source


def _parse_date(value: str, label: str, ctx) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        raise ctx.MetaOpsError(f"{label} must be YYYY-MM-DD, got {value!r}") from None


def _range_args(args, ctx) -> tuple[int | None, dt.date | None, dt.date | None]:
    """Argument-only checks, run before any network call."""
    days = getattr(args, "days", None)
    since_s, until_s = getattr(args, "since", None), getattr(args, "until", None)
    if since_s or until_s:
        if days is not None:
            raise ctx.MetaOpsError("--days and --since/--until are exclusive")
        if not (since_s and until_s):
            raise ctx.MetaOpsError("--since and --until must be given together")
        since, until = _parse_date(since_s, "--since", ctx), _parse_date(until_s, "--until", ctx)
        if since > until:
            raise ctx.MetaOpsError("--since is after --until")
        if (until - since).days + 1 > MAX_DAYS:
            raise ctx.MetaOpsError(f"range is longer than {MAX_DAYS} days; split it")
        return None, since, until
    n = DEFAULT_DAYS if days is None else days
    if n < 1 or n > MAX_DAYS:
        raise ctx.MetaOpsError(f"--days must be 1..{MAX_DAYS}")
    return n, None, None


def _zone(tz_name: str, ctx) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        raise ctx.MetaOpsError(f"unknown ad account timezone {tz_name!r} (tz database missing?)") from None


def _resolve_range(parsed: tuple[int | None, dt.date | None, dt.date | None], tz_name: str,
                   ctx) -> tuple[dt.date, dt.date]:
    """Trailing days end today IN THE AD ACCOUNT's timezone (insights dates are already there)."""
    days, since, until = parsed
    today = _utcnow().astimezone(_zone(tz_name, ctx)).date()
    if days is not None:
        return today - dt.timedelta(days=days - 1), today
    if since is None or until is None:  # pragma: no cover - _range_args guarantees one form
        raise ctx.MetaOpsError("no date range resolved")
    if until > today:
        raise ctx.MetaOpsError(f"--until {until} is after today in the account timezone ({today})")
    return since, until


def _currency_arg(args, ctx) -> str | None:
    raw = (getattr(args, "keitaro_currency", None) or os.environ.get("KEITARO_CURRENCY", "")).strip()
    if not raw:
        return None
    if len(raw) != 3 or not raw.isalpha():
        raise ctx.MetaOpsError(f"Keitaro currency must be an ISO 4217 code, got {raw!r}")
    return raw.upper()


# --------------------------------------------------------------------------- Facebook side


def _paged(ctx, path: str, params: dict[str, Any], context: str) -> list[dict[str, Any]]:
    query = dict(params, limit=PAGE_LIMIT)
    rows: list[dict[str, Any]] = []
    for _ in range(MAX_PAGES):
        resp = ctx.graph.get(path, params=query, context=context)
        rows.extend(r for r in (resp.get("data") or []) if isinstance(r, dict))
        query = ctx.graph.next_page_params(resp, query)
        if query is None:
            return rows
        _sleep(0.3)  # a read is a point of budget; do not sprint through pages
    raise ctx.MetaOpsError(f"{context}: more than {MAX_PAGES} pages; narrow the range")


def _fb_account(ctx, account: str) -> dict[str, str]:
    acct = ctx.graph.get(account, params={"fields": "timezone_name,currency"}, context="keitaro account")
    tz, currency = acct.get("timezone_name"), acct.get("currency")
    if not tz or not currency:
        raise ctx.MetaOpsError(f"{account}: Graph returned no timezone_name/currency ({acct})")
    return {"timezone": str(tz), "currency": str(currency)}


def _time_params(since: dt.date, until: dt.date) -> dict[str, Any]:
    return {"time_range": {"since": since.isoformat(), "until": until.isoformat()}, "time_increment": 1}


def _fb_ad_rows(ctx, account: str, since: dt.date, until: dt.date, fields: str) -> dict[tuple[str, str], dict[str, Any]]:
    """{(day, ad_id): row} for every ad with delivery, whatever its effective_status."""
    params = {
        "level": "ad", "fields": fields, **_time_params(since, until),
        "filtering": [{"field": "ad.effective_status", "operator": "IN",
                       "value": list(INSIGHT_EFFECTIVE_STATUSES)}],
    }
    rows = _paged(ctx, f"{account}/insights", params, "keitaro ad insights")
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for r in rows:
        ad_id, day = str(r.get("ad_id") or ""), str(r.get("date_start") or "")
        if not ad_id or not day:
            raise ctx.MetaOpsError(f"insights row without ad_id/date_start: {r}")
        if r.get("date_stop") and str(r["date_stop"]) != day:
            raise ctx.MetaOpsError(f"insights row spans several days ({day}..{r['date_stop']}); expected daily rows")
        try:
            spend = _dec(r.get("spend"), "spend")
        except ValueError as exc:
            raise ctx.MetaOpsError(f"ad {ad_id} {day}: {exc}") from None
        if (day, ad_id) in out:
            raise ctx.MetaOpsError(f"duplicate insights row for ad {ad_id} on {day}; refusing to guess")
        if not since.isoformat() <= day <= until.isoformat():
            continue
        out[(day, ad_id)] = {
            "spend": spend, "impressions": int(_dec(r.get("impressions"))),
            "link_clicks": int(_dec(r.get("inline_link_clicks"))),
            "ad_name": r.get("ad_name"), "campaign_id": str(r.get("campaign_id") or ""),
            "adset_id": str(r.get("adset_id") or ""), "adset_name": r.get("adset_name"),
        }
    return out


def _fb_day_totals(ctx, account: str, since: dt.date, until: dt.date, level: str,
                   extra_fields: str = "", filtering: list[dict[str, Any]] | None = None,
                   key: str | None = None) -> dict[Any, Decimal]:
    """Spend per day (level=account) or per (day, id) (level=campaign) straight from Graph."""
    params: dict[str, Any] = {"level": level, "fields": f"spend,date_start,date_stop{extra_fields}",
                              **_time_params(since, until)}
    if filtering:
        params["filtering"] = filtering
    out: dict[Any, Decimal] = {}
    for r in _paged(ctx, f"{account}/insights", params, f"keitaro {level} insights"):
        day = str(r.get("date_start") or "")
        try:
            spend = _dec(r.get("spend"), "spend")
        except ValueError as exc:
            raise ctx.MetaOpsError(f"{level} {day}: {exc}") from None
        k: Any = day if key is None else (day, str(r.get(key) or ""))
        out[k] = out.get(k, Decimal(0)) + spend
    return out


def _tolerance(rows: int) -> Decimal:
    """Rounding noise of `rows` two-decimal spends: half a cent each, plus a cent."""
    return Decimal("0.01") + Decimal("0.005") * rows


def attribution(ad_rows: dict[tuple[str, str], dict[str, Any]], account_days: dict[str, Decimal],
                days: list[str]) -> dict[str, Any]:
    """Account total minus the sum of ad rows, per day. Positive = spend no ad row explains."""
    per_day: dict[str, dict[str, Any]] = {}
    for day in days:
        rows = [r for (d, _), r in ad_rows.items() if d == day]
        ad_sum = sum((r["spend"] for r in rows), Decimal(0))
        total = account_days.get(day, Decimal(0))
        gap = total - ad_sum
        tol = _tolerance(len(rows))
        per_day[day] = {"ad_rows": len(rows), "ad_spend": ad_sum, "account_spend": total,
                        "unattributed": gap, "significant": abs(gap) > tol, "tolerance": tol}
    return per_day


def remainder_analysis(ad_rows: dict[tuple[str, str], dict[str, Any]],
                       campaign_days: dict[tuple[str, str], Decimal], tz: str, currency: str) -> dict[str, Any]:
    """Split the gap per (day, FB campaign). A campaign with no ad row that day can be pushed on
    `ad_campaign_id` without touching a per-ad entry; a partly explained one cannot."""
    candidates: list[dict[str, Any]] = []
    partial: list[dict[str, Any]] = []
    for (day, cid), spend in sorted(campaign_days.items()):
        rows = [r for (d, _), r in ad_rows.items() if d == day and r["campaign_id"] == cid]
        gap = spend - sum((r["spend"] for r in rows), Decimal(0))
        if gap <= _tolerance(len(rows)):
            continue
        if not rows:
            candidates.append({
                "day": day, "campaign_id": cid, "cost": _r2(spend),
                "entry": {"start_date": KT_DATE_START.format(day=day), "end_date": KT_DATE_END.format(day=day),
                          "timezone": tz, "currency": currency, "cost": float(spend),
                          "filters": {"ad_campaign_id": cid}},
            })
        else:
            partial.append({"day": day, "campaign_id": cid, "gap": _r2(gap), "ad_rows": len(rows)})
    return {"remainder_candidates": candidates, "partial_gaps": partial}


# --------------------------------------------------------------------------- Keitaro reads


def _kt_range(since: dt.date, until: dt.date, tz: str) -> dict[str, str]:
    return {"from": KT_DATE_START.format(day=since.isoformat()),
            "to": KT_DATE_END.format(day=until.isoformat()), "timezone": tz}


def _kt_report(client: KeitaroClient, campaign_id: int, since: dt.date, until: dt.date, tz: str,
               dimensions: list[str], measures: tuple[str, ...]) -> list[dict[str, Any]]:
    """POST /report/build filtered to the campaign, paged. Row keys = dimension / measure names."""
    body = {
        "range": _kt_range(since, until, tz), "dimensions": dimensions, "measures": list(measures),
        "filters": [{"name": "campaign_id", "operator": KT_EQ_OPERATOR, "expression": str(campaign_id)}],
    }
    rows: list[dict[str, Any]] = []
    for page in range(MAX_PAGES):
        resp = client.post("/report/build", {**body, "limit": KT_PAGE_LIMIT, "offset": page * KT_PAGE_LIMIT})
        chunk = resp.get("rows") if isinstance(resp, dict) else resp
        if not isinstance(chunk, list):
            raise KeitaroError("/report/build: unexpected answer shape (no rows list)",
                               path="/report/build", kind="shape")
        rows.extend(r for r in chunk if isinstance(r, dict))
        total = resp.get("total") if isinstance(resp, dict) else None
        if len(chunk) < KT_PAGE_LIMIT or (isinstance(total, int) and len(rows) >= total):
            return rows
    raise KeitaroError("/report/build: too many pages", path="/report/build", kind="shape")


def _kt_day(row: dict[str, Any]) -> str:
    """The `day` dimension as YYYY-MM-DD. Anything else would silently mismatch every FB key."""
    raw = str(row.get("day") or "")
    try:
        return dt.date.fromisoformat(raw[:10]).isoformat()
    except ValueError:
        raise KeitaroError(f"/report/build: unexpected day value {raw[:20]!r} (expected YYYY-MM-DD)",
                           path="/report/build", kind="shape") from None


def _sub_id(row: dict[str, Any]) -> str:
    return str(row.get(KT_AD_DIMENSION) if row.get(KT_AD_DIMENSION) is not None else "").strip()


def _kt_campaign(client: KeitaroClient, campaign_id: int, warnings: list[dict[str, str]]) -> dict[str, Any]:
    """GET /campaigns/{id} (read only): existence, name, and the cost model that can fake cost."""
    resp = client.get(f"/campaigns/{campaign_id}")
    if not isinstance(resp, dict):
        raise KeitaroError(f"/campaigns/{campaign_id}: unexpected answer shape",
                           path=f"/campaigns/{campaign_id}", kind="shape")
    info = {"id": campaign_id, "name": resp.get("name"), "cost_type": resp.get("cost_type"),
            "cost_value": resp.get("cost_value"), "cost_auto": resp.get("cost_auto")}
    ctype = str(info["cost_type"] or "").upper()
    auto = info["cost_auto"] in (True, 1, "1", "true", "True")
    value = _dec(info["cost_value"])
    if info["cost_type"] is None and info["cost_auto"] is None:
        _warn(warnings, "cost_model_unreadable",
              f"campaign {campaign_id}: GET /campaigns/{{id}} returned no cost_type/cost_auto; "
              "check the cost model in the UI (CPA/CPS with auto ON adds fake cost)")
    elif ctype in ("CPA", "CPS") and auto:
        _warn(warnings, "cost_model_auto",
              f"campaign {campaign_id} cost model is {ctype} {info['cost_value']} with AUTO ON: Keitaro adds "
              "that fixed cost per NEW conversion on top of the pushed cost (fake cost, wrong ROI). Re-push "
              "after late conversions, or set CPC 0 with the campaign owner's OK (tracker-ops/01)")
    elif ctype in ("CPC", "CPUC", "CPM") and value != 0:
        _warn(warnings, "cost_model_value",
              f"campaign {campaign_id} cost model is {ctype} {info['cost_value']}: Keitaro prices new clicks "
              "itself until the next push overwrites them; tracker-ops/01 recommends CPC 0")
    return info


# --------------------------------------------------------------------------- push: entries, reconcile


def build_entries(ad_rows: dict[tuple[str, str], dict[str, Any]], tz: str, currency: str) -> tuple[list[dict[str, Any]], int]:
    """One update_costs entry per (ad, day) with spend > 0. Key = ad id, never a name."""
    entries: list[dict[str, Any]] = []
    zero = 0

    def order(item: tuple[tuple[str, str], Any]) -> tuple[str, int, str]:
        (day, ad_id), _ = item
        return day, int(ad_id) if ad_id.isdigit() else 0, ad_id

    for (day, ad_id), row in sorted(ad_rows.items(), key=order):
        if row["spend"] <= 0:
            zero += 1
            continue
        entries.append({
            "start_date": KT_DATE_START.format(day=day), "end_date": KT_DATE_END.format(day=day),
            "timezone": tz, "currency": currency, "cost": float(row["spend"]),
            "filters": {KT_AD_DIMENSION: ad_id},
        })
    return entries, zero


def build_payloads(campaign_id: int, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One request per day (a failure stays local to a day), split further at ENTRY_CHUNK."""
    by_day: dict[str, list[dict[str, Any]]] = {}
    for e in entries:
        by_day.setdefault(e["start_date"][:10], []).append(e)
    out = []
    for day in sorted(by_day):
        costs = by_day[day]
        for i in range(0, len(costs), ENTRY_CHUNK):
            out.append({"day": day, "body": {
                "campaign_ids": [campaign_id], "only_campaign_uniques": False,
                "costs": costs[i:i + ENTRY_CHUNK]}})
    return out


def reconcile(days: list[str], entries: list[dict[str, Any]], kt_rows: list[dict[str, Any]],
              converted: bool) -> dict[str, Any]:
    """FB spend pushed vs what Keitaro reports for the same (day, ad).

    Per day: fb (sum of pushed entries), kt (Keitaro cost on those ads), delta, and the spend of
    ad-days with ZERO Keitaro clicks (`lost`: no click to carry the cost, it is dropped). Flags:
    no_clicks (lost > 0), not_stored (fb > 0, kt == 0), delta (|delta| > 3%). A day is `settled`
    when what could land (fb - lost) is within tolerance of kt. With `converted` the Keitaro
    currency differs from the account's: kt is scaled by the median implied rate, so delta shows
    inconsistency between days, not the FX rate itself."""
    fb: dict[tuple[str, str], Decimal] = {}
    for e in entries:
        fb[(e["start_date"][:10], e["filters"][KT_AD_DIMENSION])] = Decimal(str(e["cost"]))
    kt: dict[tuple[str, str], dict[str, Decimal]] = {}
    other: dict[str, dict[str, Decimal]] = {}
    for r in kt_rows:
        day, ad = _kt_day(r), _sub_id(r)
        target = (kt.setdefault((day, ad), {"clicks": Decimal(0), "cost": Decimal(0)}) if (day, ad) in fb
                  else other.setdefault(day, {"clicks": Decimal(0), "cost": Decimal(0)}))
        target["clicks"] += _dec(r.get("clicks"))
        target["cost"] += _dec(r.get("cost"))

    rate = Decimal(1)
    if converted:
        ratios = []
        for day in days:
            f = sum((v for (d, _), v in fb.items() if d == day), Decimal(0))
            k = sum((v["cost"] for (d, _), v in kt.items() if d == day), Decimal(0))
            if f > 0 and k > 0:
                ratios.append(k / f)
        rate = Decimal(str(statistics.median(ratios))) if ratios else Decimal(0)

    rows: list[dict[str, Any]] = []
    no_clicks: list[dict[str, Any]] = []
    short: list[dict[str, Any]] = []
    for day in days:
        keys = sorted(k for k in fb if k[0] == day)
        f = sum((fb[k] for k in keys), Decimal(0))
        k_cost = sum((kt.get(k, {}).get("cost", Decimal(0)) for k in keys), Decimal(0))
        clicks = sum((kt.get(k, {}).get("clicks", Decimal(0)) for k in keys), Decimal(0))
        eq = k_cost / rate if rate else Decimal(0)
        lost = Decimal(0)
        for k in keys:
            got = kt.get(k, {"clicks": Decimal(0), "cost": Decimal(0)})
            if got["clicks"] <= 0:
                lost += fb[k]
                no_clicks.append({"day": day, "ad_id": k[1], "spend": _r2(fb[k])})
            elif fb[k] > 0 and rate and abs(got["cost"] / rate - fb[k]) > fb[k] * Decimal(str(DELTA_FLAG_PCT)) / 100:
                short.append({"day": day, "ad_id": k[1], "fb_spend": _r2(fb[k]),
                              "keitaro_cost": _r2(got["cost"]), "keitaro_clicks": int(got["clicks"])})
        delta = eq - f
        delta_pct = float(delta / f * 100) if f else None
        storable = f - lost
        settled = (not f) or abs(storable - eq) <= max(storable * Decimal(str(DELTA_FLAG_PCT)) / 100, Decimal("0.01"))
        flags = []
        if lost > 0:
            flags.append("no_clicks")
        if f > 0 and k_cost == 0:
            flags.append("not_stored")
        if delta_pct is not None and abs(delta_pct) > DELTA_FLAG_PCT:
            flags.append("delta")
        o = other.get(day, {"clicks": Decimal(0), "cost": Decimal(0)})
        rows.append({
            "day": day, "fb_spend": _r2(f), "keitaro_cost": _r2(eq) if converted else _r2(k_cost),
            "keitaro_cost_raw": _r2(k_cost), "delta": _r2(delta),
            "delta_pct": round(delta_pct, 2) if delta_pct is not None else None,
            "keitaro_clicks": int(clicks), "lost_no_clicks": _r2(lost), "settled": settled, "flags": flags,
            "other_cost": _r2(o["cost"]), "other_clicks": int(o["clicks"]),
        })
    return {
        "days": rows, "settled": all(r["settled"] for r in rows),
        "fx_rate": float(rate) if converted else None, "converted": converted,
        "no_clicks": _capped(no_clicks), "short": _capped(short),
    }


# --------------------------------------------------------------------------- push: output


def _print_entries(entries: list[dict[str, Any]], ad_rows: dict[tuple[str, str], dict[str, Any]]) -> None:
    if not entries:
        _say("  (no entries: no ad had spend in this range)")
        return
    rows = []
    for e in entries:
        ad = e["filters"][KT_AD_DIMENSION]
        name = str(ad_rows[(e["start_date"][:10], ad)].get("ad_name") or "")
        rows.append([e["start_date"][:10], ad, f"{e['cost']:.2f}", e["currency"], name[:40]])
    _say(_table(["day", "sub_id_6 (ad id)", "cost", "cur", "ad name (display only)"], rows, left=2))


def _print_days(rec: dict[str, Any], attr: dict[str, dict[str, Any]], title: str) -> None:
    rows = []
    for d in rec["days"]:
        a = attr.get(d["day"], {})
        rows.append([
            d["day"], _fmt(_r2(a.get("account_spend"))), _fmt(_r2(a.get("unattributed"))),
            _fmt(d["fb_spend"]), _fmt(d["keitaro_cost"]), _fmt(d["delta"]),
            "-" if d["delta_pct"] is None else f"{d['delta_pct']:+.1f}%",
            str(d["keitaro_clicks"]), _fmt(d["lost_no_clicks"]), ",".join(d["flags"]) or "ok",
        ])
    _say(title)
    _say(_table(["day", "fb_account", "unattrib", "fb_pushed", "keitaro", "delta", "delta%",
                 "kt_clicks", "no_click_$", "flags"], rows))


def _write_payload_file(workspace, account: str, ctx, meta: dict[str, Any],
                        payloads: list[dict[str, Any]]) -> str:
    out_dir = (workspace.state_root / "keitaro").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"push-{account}-{_stamp(ctx)}.json"
    doc = {"schema": PUSH_SCHEMA, **meta, "requests": [{"day": p["day"], "body": p["body"]} for p in payloads]}
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return str(path)


def _failure(ctx, phase: str, exc: KeitaroError, code: int = 1, data: dict[str, Any] | None = None,
             next_action: str | None = None,
             artifacts: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
    return code, ctx.result_envelope(RESULT_COMMAND, False, phase, artifacts=artifacts, data=data,
                                     error=exc.as_dict(), next_action=next_action)


# --------------------------------------------------------------------------- push command


def command_push(args, ctx) -> tuple[int, dict[str, Any]]:
    workspace, pname, profile = _profile(ctx, args, "keitaro push")
    account = ctx.graph.normalize_account(profile["ad_account_id"])
    confirm = getattr(args, "confirm", None)
    if confirm is not None and confirm != "PUSH":
        raise ctx.MetaOpsError("keitaro push requires the literal --confirm PUSH (omit --confirm for a dry run)")
    live = confirm == "PUSH"
    campaign_id, campaign_source = _campaign_id(args, pname, profile, ctx)
    parsed = _range_args(args, ctx)
    kt_currency = _currency_arg(args, ctx)
    wait = READBACK_WAIT_DEFAULT if getattr(args, "readback_wait", None) is None else args.readback_wait
    if wait < 0:
        raise ctx.MetaOpsError("--readback-wait must be >= 0")
    try:
        client = _make_client(ctx)
    except KeitaroError as exc:
        return _failure(ctx, "credentials", exc, code=2)

    warnings: list[dict[str, str]] = []
    _say(f"keitaro push ({'LIVE' if live else 'DRY RUN'}) {account} -> Keitaro campaign {campaign_id}")
    try:
        campaign = _kt_campaign(client, campaign_id, warnings)
    except KeitaroError as exc:
        return _failure(ctx, "campaign_read", exc,
                        next_action="Nothing was pushed. Check KEITARO_URL/KEITARO_API_KEY and the campaign id.")

    acct = _fb_account(ctx, account)
    tz, currency = acct["timezone"], acct["currency"]
    for key, live_value in (("timezone", tz), ("currency", currency)):
        if profile.get(key) and str(profile[key]) != live_value:
            _warn(warnings, f"profile_{key}",
                  f"profile {key} {profile[key]!r} differs from the account's {live_value!r}; using the account's")
    since, until = _resolve_range(parsed, tz, ctx)
    days = _daterange(since, until)
    partial_today = until == _utcnow().astimezone(_zone(tz, ctx)).date()
    converted = bool(kt_currency and kt_currency != currency.upper())
    _say(f"  {account} tz={tz} currency={currency}  {since}..{until}  campaign {campaign_id} "
         f"{campaign.get('name') or ''!r}")

    ad_rows = _fb_ad_rows(ctx, account, since, until, AD_FIELDS_PUSH)
    account_days = _fb_day_totals(ctx, account, since, until, "account")
    attr = attribution(ad_rows, account_days, days)
    gap_days = [d for d, a in attr.items() if a["significant"]]
    remainder: dict[str, Any] = {"remainder_candidates": [], "partial_gaps": []}
    if any(attr[d]["unattributed"] > 0 for d in gap_days):
        try:  # diagnostics only: a failure here must not block the per-ad push
            campaign_days = _fb_day_totals(
                ctx, account, since, until, "campaign", ",campaign_id", key="campaign_id",
                filtering=[{"field": "campaign.effective_status", "operator": "IN",
                            "value": list(CAMPAIGN_EFFECTIVE_STATUSES)}])
            remainder = remainder_analysis(ad_rows, campaign_days, tz, currency)
        except ctx.graph.GraphError as exc:
            _warn(warnings, "campaign_breakdown_failed",
                  f"campaign-level breakdown of the unattributed spend failed: {ctx.graph.redact(str(exc))[:200]}")
    unattributed_total = sum((attr[d]["unattributed"] for d in gap_days if attr[d]["unattributed"] > 0), Decimal(0))
    over_days = [d for d in gap_days if attr[d]["unattributed"] < 0]
    under_days = [d for d in gap_days if attr[d]["unattributed"] > 0]
    if under_days:
        _warn(warnings, "unattributed",
              f"UNATTRIBUTED SPEND {_r2(unattributed_total)} {currency} on {len(under_days)} day(s) "
              f"({', '.join(under_days)}): the account total is not explained by the ad rows. It is NOT pushed "
              "(a campaign-level entry would overwrite the per-ad costs of the same clicks)")
        for c in remainder["remainder_candidates"]:
            _say(f"    candidate, campaign {c['campaign_id']} {c['day']}: {c['cost']} {currency} "
                 "(no ad row at all that day; pushable on ad_campaign_id without overwriting anything)")
        for c in remainder["partial_gaps"]:
            _say(f"    campaign {c['campaign_id']} {c['day']}: {c['gap']} {currency} missing next to "
                 f"{c['ad_rows']} ad row(s); not pushable safely")
    if over_days:
        _warn(warnings, "ad_rows_exceed_account",
              f"ad rows exceed the account total on {', '.join(over_days)}; a duplicated or foreign row? "
              "Check before pushing")

    entries, zero_rows = build_entries(ad_rows, tz, currency)
    payloads = build_payloads(campaign_id, entries)
    total = sum((Decimal(str(e["cost"])) for e in entries), Decimal(0))
    _say(f"  {len(entries)} entries in {len(payloads)} request(s), total {_r2(total)} {currency}"
         f"; {zero_rows} zero-spend rows skipped")
    if partial_today:
        _say(f"  {until} is a partial day in {tz}: cost lands only on clicks that exist now; the next run's "
             "overwrite completes it")
    if kt_currency is None:
        _say(f"  Keitaro base currency not given (--keitaro-currency / KEITARO_CURRENCY): assuming it equals "
             f"the account's {currency}; if not, delta below is FX")
    elif converted:
        _say(f"  Keitaro currency {kt_currency} != account {currency}: delta is judged against the median "
             "implied FX rate, not against 1.0")

    artifact = _write_payload_file(
        workspace, account, ctx,
        {"account_id": account, "profile": pname, "keitaro_campaign": campaign_id, "live": live,
         "timezone": tz, "currency": currency, "since": since.isoformat(), "until": until.isoformat()},
        payloads)
    _say("\nupdate_costs entries" + (" (about to be sent):" if live else " (dry run, NOT sent):"))
    _print_entries(entries, ad_rows)

    data: dict[str, Any] = {
        "account_id": account, "profile": pname, "mode": "live" if live else "dry_run",
        "timezone": tz, "currency": currency, "keitaro_currency": kt_currency or currency,
        "keitaro_currency_assumed": kt_currency is None,
        "since": since.isoformat(), "until": until.isoformat(), "includes_partial_today": partial_today,
        "keitaro_campaign": {**campaign, "source": campaign_source},
        "entries_count": len(entries), "entries_total": _r2(total), "zero_spend_rows_skipped": zero_rows,
        "requests": len(payloads),
        "unattributed": {
            "total": _r2(unattributed_total),
            "days": {d: {"account_spend": _r2(a["account_spend"]), "ad_spend": _r2(a["ad_spend"]),
                         "unattributed": _r2(a["unattributed"]), "significant": a["significant"]}
                     for d, a in attr.items()},
            **remainder,
        },
    }
    if not live:
        data["entries"] = entries

    pushed_days: list[str] = []
    if live and payloads:
        for i, p in enumerate(payloads):
            try:
                resp = client.post("/clicks/update_costs", p["body"], write=True)
                if isinstance(resp, dict) and resp.get("success") is False:
                    raise KeitaroError(f"update_costs refused day {p['day']}: {json.dumps(resp)[:300]}",
                                       path="/clicks/update_costs", kind="refused")
            except KeitaroError as exc:
                pending = sorted({q["day"] for q in payloads[i:]})
                data["pushed"] = {"requests": i, "days": sorted(set(pushed_days)), "failed_day": p["day"],
                                  "pending_days": pending}
                return _failure(
                    ctx, "push_failed", exc, data=data, artifacts={"payload": artifact}, next_action=(
                        "Not retried. Re-running the same command is safe (overwrite is idempotent)."
                        + (" The failed request may still be running inside Keitaro: run the dry run first "
                           "and read what it stored." if exc.outcome_unknown else "")))
            pushed_days.append(p["day"])
            _say(f"  pushed {p['day']} ({len(p['body']['costs'])} entries)")
        data["pushed"] = {"requests": len(payloads), "days": sorted(set(pushed_days)), "pending_days": []}

    readback: dict[str, Any] = {"checked": False}
    rec: dict[str, Any] | None = None
    if entries:
        elapsed = 0
        attempts = 0
        try:
            while True:
                attempts += 1
                kt_rows = _kt_report(client, campaign_id, since, until, tz,
                                     ["day", KT_AD_DIMENSION], KT_MEASURES_COST)
                rec = reconcile(days, entries, kt_rows, converted)
                if not live or rec["settled"] or elapsed >= wait:
                    break
                _say(f"  readback not settled yet ({elapsed}s); Keitaro applies costs asynchronously, "
                     f"polling every {READBACK_POLL}s (no re-push)")
                step = min(READBACK_POLL, wait - elapsed)
                _sleep(step)
                elapsed += step
            readback = {"checked": True, "attempts": attempts, "waited_s": elapsed,
                        "settled": rec["settled"], "fx_rate": rec["fx_rate"]}
        except KeitaroError as exc:
            readback = {"checked": False, "error": exc.as_dict()}
            _warn(warnings, "readback_failed",
                  f"Keitaro readback failed ({exc.message}); "
                  + ("the push itself went through" if live else "the dry run cannot show what Keitaro stores now"))
    data["readback"] = readback
    if rec is not None:
        data["reconcile"] = rec
        _print_days(rec, attr, "\nFB spend vs Keitaro cost per day "
                              + ("(Keitaro cost as read back after the push)" if live
                                 else "(Keitaro cost NOW, before any push)"))
        if rec["no_clicks"]:
            lost = sum((Decimal(str(x["spend"])) for x in rec["no_clicks"]), Decimal(0))
            _warn(warnings, "no_clicks",
                  f"{len(rec['no_clicks'])} ad-day(s), {_r2(lost)} {currency}: FB spend but ZERO Keitaro clicks with "
                  "that sub_id_6 in the range; update_costs spreads cost over matching clicks only, so this "
                  "spend is lost from Keitaro ROI (wrong campaign/mapping, or the ad's clicks never reached Keitaro)")
        if live and not rec["settled"]:
            _warn(warnings, "readback_pending",
                  "Keitaro cost does not match yet. Readback lags (seconds to ~20 min): this is NOT a failure; "
                  "re-read later with the dry run and do not re-push. It also stays short if update_costs skips "
                  "bot-marked clicks (unverified for the API)")
    if not entries:
        phase = "nothing_to_push" if live else "dry_run"
    else:
        phase = "pushed" if live else "dry_run"
    data["warnings"] = warnings
    if not live:
        next_action = "Nothing was written to Keitaro. To push these entries re-run with --confirm PUSH."
    elif not entries:
        next_action = "No ad had spend in the range; nothing was sent."
    elif rec is not None and rec["settled"]:
        next_action = "Costs stored. Re-push the trailing days on every run (overwrite is idempotent)."
    else:
        next_action = ("Pushed. Keitaro applies costs asynchronously: re-read in ~10-20 min with the dry run "
                       "(prints Keitaro cost now), do not re-push.")
    caveats = []
    if rec is not None and rec["no_clicks"]:
        caveats.append(f"{len(rec['no_clicks'])} ad-day(s) had no Keitaro clicks: that spend is not in Keitaro (no_clicks)")
    if under_days:
        caveats.append(f"unattributed spend {_r2(unattributed_total)} {currency} was not pushed (unattributed)")
    if caveats:
        next_action += " Not fully accounted for: " + "; ".join(caveats) + "."
    return 0, ctx.result_envelope(RESULT_COMMAND, True, phase, artifacts={"payload": artifact},
                                  data=data, next_action=next_action)


# --------------------------------------------------------------------------- report: join


def _bucket() -> dict[str, Any]:
    return {"fb_spend": Decimal(0), "fb_link_clicks": 0, "fb_impressions": 0,
            **{m: Decimal(0) for m in KT_MEASURES_JOIN}, "ads": set()}


def _derive(b: dict[str, Any]) -> dict[str, Any]:
    regs = b["leads"] + b["sales"]
    deps = b["sales"]
    cost, revenue = b["cost"], b["sale_revenue"]
    return {
        "fb_spend": _r2(b["fb_spend"]), "fb_link_clicks": b["fb_link_clicks"],
        "clicks": int(b["clicks"]), "leads": int(b["leads"]), "sales": int(b["sales"]),
        "regs": int(regs), "deps": int(deps), "cost": _r2(cost), "sale_revenue": _r2(revenue),
        "lead_revenue": _r2(b["lead_revenue"]),
        "cost_per_reg": _r2(cost / regs) if regs else None,
        "cost_per_dep": _r2(cost / deps) if deps else None,
        "roi_pct": round(float((revenue - cost) / cost * 100), 1) if cost > 0 else None,
    }


def join_report(fb_rows: dict[tuple[str, str], dict[str, Any]], kt_rows: list[dict[str, Any]],
                by: str) -> dict[str, Any]:
    """FB spend per ad joined with Keitaro per sub_id_6. Never touches `conversions`."""
    meta: dict[str, dict[str, Any]] = {}
    for (_, ad_id), r in sorted(fb_rows.items()):
        meta[ad_id] = r  # latest day wins for the display name

    def key_of(day: str | None, ad_id: str) -> tuple[str, str]:
        if by == "day":
            return day or "?", day or "?"
        m = meta.get(ad_id)
        if by == "adset":
            if not m or not m["adset_id"]:
                return "(not in FB rows)", "ads Keitaro has but FB reported no spend for"
            return m["adset_id"], str(m.get("adset_name") or "")
        return ad_id, str(m["ad_name"] or "") if m else ""

    buckets: dict[str, dict[str, Any]] = {}
    labels: dict[str, str] = {}
    fb_seen: set[str] = set()
    for (day, ad_id), r in fb_rows.items():
        k, label = key_of(day, ad_id)
        b = buckets.setdefault(k, _bucket())
        labels.setdefault(k, label)
        b["fb_spend"] += r["spend"]
        b["fb_link_clicks"] += r["link_clicks"]
        b["fb_impressions"] += r["impressions"]
        b["ads"].add(ad_id)
        fb_seen.add(k)

    excluded = {"macro": _bucket(), "empty": _bucket()}
    macro_values: set[str] = set()
    lead_revenue_all = Decimal(0)
    for r in kt_rows:
        sub = _sub_id(r)
        values = {m: _dec(r.get(m)) for m in KT_MEASURES_JOIN}
        lead_revenue_all += values["lead_revenue"]
        if not sub:
            target = excluded["empty"]
        elif "{{" in sub or "}}" in sub:
            macro_values.add(sub)
            target = excluded["macro"]
        else:
            day = _kt_day(r) if by == "day" else None
            k, label = key_of(day, sub)
            target = buckets.setdefault(k, _bucket())
            labels.setdefault(k, label)
            target["ads"].add(sub)
        for m, v in values.items():
            target[m] += v

    rows = []
    total = _bucket()
    for k, b in buckets.items():
        row = {"key": k, "label": labels.get(k, ""), "ads": len(b["ads"]), **_derive(b)}
        flags = []
        if by == "ad":
            if k not in fb_seen:
                flags.append("not_in_fb_rows")
            elif b["clicks"] == 0:
                flags.append("no_keitaro_clicks")
            if b["fb_spend"] > 0 and b["clicks"] > 0 and b["cost"] == 0:
                flags.append("no_keitaro_cost")
        row["flags"] = flags
        rows.append(row)
        for m in ("fb_spend", *KT_MEASURES_JOIN):
            total[m] += b[m]
        total["fb_link_clicks"] += b["fb_link_clicks"]
        total["fb_impressions"] += b["fb_impressions"]
        total["ads"] |= b["ads"]
    if by == "day":
        rows.sort(key=lambda r: r["key"])
    else:
        rows.sort(key=lambda r: (-(r["fb_spend"] or 0), -(r["cost"] or 0)))
    lead_rev = _r2(lead_revenue_all)
    return {
        "by": by, "rows": rows, "totals": {"ads": len(total["ads"]), **_derive(total)},
        "excluded": {
            "unsubstituted_macros": {**_derive(excluded["macro"]), "distinct_values": len(macro_values),
                                     "examples": sorted(macro_values)[:5]},
            "empty_sub_id_6": _derive(excluded["empty"]),
        },
        "lead_revenue_total": lead_rev,
    }


def _print_report(result: dict[str, Any], currency: str) -> None:
    rows = []
    for r in result["rows"][:60]:
        rows.append([
            r["key"][-12:] if result["by"] != "day" else r["key"], r["label"][:24],
            _fmt(r["fb_spend"]), str(r["clicks"]), str(r["regs"]), str(r["deps"]), _fmt(r["cost"]),
            _fmt(r["cost_per_reg"]), _fmt(r["cost_per_dep"]), _fmt(r["sale_revenue"]),
            "-" if r["roi_pct"] is None else f"{r['roi_pct']:+.0f}%", ",".join(r["flags"]),
        ])
    t = result["totals"]
    rows.append(["TOTAL", "", _fmt(t["fb_spend"]), str(t["clicks"]), str(t["regs"]), str(t["deps"]),
                 _fmt(t["cost"]), _fmt(t["cost_per_reg"]), _fmt(t["cost_per_dep"]), _fmt(t["sale_revenue"]),
                 "-" if t["roi_pct"] is None else f"{t['roi_pct']:+.0f}%", ""])
    _say(f"\nby {result['by']}: fb_spend in {currency}; cost/sale_revenue in Keitaro's base currency")
    _say(_table(["key", "name", "fb_spend", "clicks", "regs", "deps", "cost", "c/reg", "c/dep",
                 "sale_rev", "roi", "flags"], rows, left=2))
    if len(result["rows"]) > 60:
        _say(f"  ... {len(result['rows']) - 60} more rows in the JSON result")
    ex = result["excluded"]
    for label, e in (("unsubstituted {{...}} macros", ex["unsubstituted_macros"]),
                     ("empty sub_id_6", ex["empty_sub_id_6"])):
        if e["clicks"] or e["cost"]:
            _say(f"  excluded, {label}: {e['clicks']} clicks, cost {_fmt(e['cost'])}, "
                 f"{e['regs']} regs, {e['deps']} deps, sale_revenue {_fmt(e['sale_revenue'])}")


# --------------------------------------------------------------------------- report command


def command_report(args, ctx) -> tuple[int, dict[str, Any]]:
    _, pname, profile = _profile(ctx, args, "keitaro report")
    account = ctx.graph.normalize_account(profile["ad_account_id"])
    campaign_id, campaign_source = _campaign_id(args, pname, profile, ctx)
    parsed = _range_args(args, ctx)
    by = getattr(args, "by", None) or "ad"
    if by not in ("ad", "adset", "day"):
        raise ctx.MetaOpsError("--by must be ad, adset or day")
    try:
        client = _make_client(ctx)
    except KeitaroError as exc:
        return _failure(ctx, "credentials", exc, code=2)

    warnings: list[dict[str, str]] = []
    try:
        campaign = _kt_campaign(client, campaign_id, warnings)
    except KeitaroError as exc:
        return _failure(ctx, "campaign_read", exc)
    acct = _fb_account(ctx, account)
    tz, currency = acct["timezone"], acct["currency"]
    since, until = _resolve_range(parsed, tz, ctx)
    _say(f"keitaro report {account} tz={tz} {currency} {since}..{until} campaign {campaign_id} "
         f"{campaign.get('name') or ''!r} by {by}")

    fb_rows = _fb_ad_rows(ctx, account, since, until, AD_FIELDS_REPORT)
    dims = ["day", KT_AD_DIMENSION] if by == "day" else [KT_AD_DIMENSION]
    try:
        kt_rows = _kt_report(client, campaign_id, since, until, tz, dims, KT_MEASURES_JOIN)
    except KeitaroError as exc:
        return _failure(ctx, "report_failed", exc)
    try:
        result = join_report(fb_rows, kt_rows, by)
    except KeitaroError as exc:  # a report row of an unexpected shape
        return _failure(ctx, "report_failed", exc)

    if result["lead_revenue_total"]:
        _warn(warnings, "lead_revenue",
              f"lead_revenue is {result['lead_revenue_total']}, expected 0: the network pays on the lead "
              "postback, so `revenue`/ROI from Keitaro would be fake. Money here is sale_revenue only")
    macro = result["excluded"]["unsubstituted_macros"]
    if macro["clicks"]:
        _warn(warnings, "macros",
              f"{macro['clicks']} clicks carry an unsubstituted {{{{...}}}} macro in {KT_AD_DIMENSION} "
              f"({macro['distinct_values']} distinct value(s), e.g. {macro['examples'][:2]}); excluded. Check the "
              "campaign URL template before blaming bots")
    _print_report(result, currency)
    _say("  Keitaro report basis (click date vs conversion date) is an instance setting this command "
         "does not read (tracker-ops/01).")

    return 0, ctx.result_envelope(
        RESULT_COMMAND, True, "reported",
        data={"account_id": account, "profile": pname, "timezone": tz, "currency": currency,
              "since": since.isoformat(), "until": until.isoformat(),
              "keitaro_campaign": {**campaign, "source": campaign_source},
              "warnings": warnings, **result},
        next_action="regs = leads + sales, deps = sales, ROI on sale_revenue; judge on matured click cohorts "
                    "(3-7 days), not on today.")


def command_keitaro(args, ctx) -> tuple[int, dict[str, Any]]:
    if args.keitaro_mode == "push":
        return command_push(args, ctx)
    return command_report(args, ctx)


# --------------------------------------------------------------------------- registration


def _add_common(p: argparse.ArgumentParser) -> None:
    # SUPPRESS: an unset sub-level --profile must not overwrite the global `--profile` value.
    p.add_argument("--profile", default=argparse.SUPPRESS,
                   help="workspace profile (also accepted before the subcommand)")
    p.add_argument("--days", type=int, default=None,
                   help=f"trailing days in the ad account timezone, today included (default {DEFAULT_DAYS}, max {MAX_DAYS})")
    p.add_argument("--since", help="YYYY-MM-DD, account timezone (with --until)")
    p.add_argument("--until", help="YYYY-MM-DD, account timezone (with --since)")
    p.add_argument("--keitaro-campaign", dest="keitaro_campaign",
                   help="Keitaro campaign id; default: profile field keitaro_campaign_id")


def register(sub, ctx) -> None:
    p = sub.add_parser("keitaro", help="Facebook -> Keitaro cost push and per-ad spend/regs/deps join")
    ksub = p.add_subparsers(dest="keitaro_action", required=True)

    push = ksub.add_parser("push", help="push per-ad FB spend as Keitaro cost (dry run without --confirm PUSH)")
    _add_common(push)
    push.add_argument("--keitaro-currency", dest="keitaro_currency",
                      help="Keitaro base currency (default env KEITARO_CURRENCY; unset = assumed equal to the "
                           "account currency)")
    push.add_argument("--readback-wait", dest="readback_wait", type=int, default=None,
                      help=f"seconds to poll the Keitaro readback after a push (default {READBACK_WAIT_DEFAULT})")
    push.add_argument("--confirm", help="literal PUSH to write; without it: dry run")
    push.set_defaults(handler=lambda args: command_keitaro(args, ctx), keitaro_mode="push")

    rep = ksub.add_parser("report", help="join FB spend with Keitaro clicks/regs/deps/sale_revenue per ad")
    _add_common(rep)
    rep.add_argument("--by", choices=["ad", "adset", "day"], default="ad")
    rep.set_defaults(handler=lambda args: command_keitaro(args, ctx), keitaro_mode="report")
