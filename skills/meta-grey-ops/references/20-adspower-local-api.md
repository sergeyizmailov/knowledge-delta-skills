# 20 — AdsPower Local API: profile mechanics

Reviewed 2026-09-22 against official docs (`localapi-doc-en.adspower.com`). Field findings from
one live session, one AdsPower build, macOS, 2026-09-21/22. Tool-mechanics layer under `01` —
IP/session discipline, checkpoints, freeze protocol stay there; this file is just "how not to
shoot yourself with the Local API."

## Base / auth / rate limit

- Base URL `http://local.adspower.net:50325/` or `http://localhost:50325/`, port 50325 default
  [official]; re-readable from the `local_api` config file under `adspower_global/cwd_global/
  source/` per OS if changed.
- Rate limit [official, ≥2.8.2.1]: tiered by profile count — 0–200 profiles 2 req/s, 200–5,000
  → 5 req/s, >5,000 → 10 req/s — but docs also say "certain requests are limited to 1 req/sec"
  without naming which. Field-observed 2026-09-21/22: `user/create`/`user/update` sent faster
  than ~1/sec started failing — treat both as under that 1 req/sec cap regardless of tier.
  🔺 confirm on your build; older releases may be flat 1 req/sec for everything.
- 🔺 **The rate limit fails as a SUCCESS-shaped response — a guard that fails OPEN.**
  Over-fast calls return HTTP 200 with `{"code":-1,"msg":"Too many request per second, please
  check"}`. Code that only reads `data.list` and ignores `code` sees an empty list and concludes
  "not signed in" / "no groups" — the wrong conclusion, delivered with a 200. This is
  security-relevant, not a nuisance: it broke BOTH of our own guard scripts this session, each on
  a check meant to be a hard gate (field-observed 2026-09-22). Rule: check `code == 0` on every
  call before trusting the body, not just on `user/list`; retry 2-3 times with ~1.5 s spacing
  before treating a result as real.
- Optional bearer auth: `Authorization: Bearer <key>` when "no-interface api-key" security is
  enabled [official].

## No identity endpoint: which SEAT am I on?

🔺 There is **no whoami**. Verified against the full Local API doc tree 2026-09-22: no
`user/info`, `account`, `member`, `me`, `login-status`, `team` or `subscription` endpoint exists
in v1 or v2. `GET /status` is a bare health check returning `{"code":0,"msg":"success"}`
[official] — it says the API process is reachable, nothing about who is signed in, and it does
not distinguish "running but signed out" from "signed in".

🔺 Terminology trap: AdsPower's **"user" means browser PROFILE, not login account**.
`/api/v1/user/list` is "Query Profile" [official]. Reading it as an account list is a misread;
several third-party summaries claim a members endpoint that does not exist on the live docs.

Practical seat check for an operator who runs several jobs from several AdsPower accounts:
`group/list` and the profiles under it are team-scoped — "data for each team is completely
isolated", and switching teams forces a logout/login cycle [official, help.adspower.com]. So
**the expected group being present is the available proxy for "the expected account is signed
in"**. That is an inference from the team-isolation model, not a documented property of
`group/list`, so a guard built on it fails OPEN if AdsPower ever changes the scoping — treat a
match as evidence, not proof, and never as a licence to skip looking at the UI before
destructive work.

## create vs update: the domain_name / platform trap

v1 (`/api/v1/user/create`, `/api/v1/user/update`) both take `domain_name` [official, both
endpoints' pages]. v2 (`/api/v2/browser-profile/create`) renames it `platform` and renames
`open_urls` to `tabs` [official] — v1/v2 field sets are not interchangeable.
Field-observed 2026-09-21: a `create` call on the build in use rejected `platform` with error
text literally *"When username or password or fakey have values, platform(domain_name) cannot
be empty"* — the message conflates both names. Root cause is version drift (v1 vs v2 naming),
not a single universal create/update asymmetry — don't assume it generalizes. 🔺 Confirm which
API version your integration targets before writing payloads; don't mix a v2 sample into a v1
call.
`create` also hard-requires a full `user_proxy_config` object even for no real proxy
[field-observed] — required sub-field `proxy_soft`; optional `proxy_type` (http/https/socks5),
`proxy_host`, `proxy_port`, `proxy_user`, `proxy_password`, `proxy_url` (mobile rotation link),
`global_config` (0/1) [official]. Omitting it on create is what produces the error above, not a
proxy fault.

## `open_urls` / `tabs` — the false "banned" signal

[official] Both are documented to fall back to opening the profile's `domain_name`/`platform`
URL when empty — not a blank tab. 🔺 Field-observed 2026-09-21/22 (this build): an empty
`open_urls` opened a genuinely blank tab; Facebook only appeared if history happened to hold it
— reads as "banned," isn't. Documented fallback did not occur in practice. Always pass
`open_urls`/`tabs` explicitly (the Ads Manager URL); never rely on the fallback.

## What `user/list` can't tell you

`user/list` never returns the `cookie` field — not for new profiles, not for known-good working
ones (field-observed 2026-09-22). Its absence says nothing about whether cookies loaded; don't
read a missing `cookie` key as "no cookies set." There is also no `user/detail` endpoint (404,
field-observed 2026-09-22) — no way to fetch one profile's full record either. Combined with the
fingerprint gap below, several important profile properties simply cannot be read back over the
API at all — verify by opening the profile, not by querying it.

## Probing the API without burning a proxy

`user_proxy_config: {"proxy_soft": "no_proxy"}` is accepted on `create` (field-observed
2026-09-22) — a throwaway profile costs nothing, so unknown API vocabulary (like the OS strings
below) can be probed with a disposable profile instead of a real proxy slot. Clean up with
`user/delete`, which takes a batch — `{"user_ids": [...]}` with many ids in one call, returns
`{"code":0,"msg":"Success"}` (field-observed 2026-09-22).

## Fingerprint pinning — `ua_type`/`os` shorthand

Official field: `fingerprint_config.random_ua.ua_system_version` (list, e.g. `["Windows 10"]`),
alongside `ua_browser`/`ua_version`. **Create-only** — docs state update "does not currently
support specifying browser type, system, version via this method" [official]; a wrong OS/UA pin
needs a new profile, not an update. Unset → "random in all systems by default," list includes
Android/iOS alongside Windows/Mac/Linux [official] — **confirms** the 2026-09-21 field
observation that an unpinned profile can get a mobile fingerprint, contradicting a desktop Ads
Manager session. Pin it: `"random_ua": {"ua_system_version": ["Windows 10", "Windows 11", "Mac OS X"]}` — a
desktop-only list still varies per profile, so a batch does not look like one machine.

🔺 **Accepted values, checked against the live API 2026-09-22**: `Windows 10`, `Windows 11`,
`Mac OS X` succeed; `macOS` fails with `Cannot find the UA matching system and version`. The
API therefore VALIDATES this key — which is the trap: `ua_type`/`os` are not real fields and
are accepted **silently**, so a payload pinning those looks like it worked and yields a random
OS including Android/iOS. Field-observed 2026-09-22: 9 profiles created that way had to be
deleted and rebuilt, because there is also **no endpoint that reads a profile's fingerprint
back** (`user/list` omits `fingerprint_config`; there is no `user/detail`). Pin at create,
verify by opening the profile, or not at all.

## Locale should track the proxy, not the operator

`fingerprint_config.language` (default `["en-US","en"]`) only applies when `language_switch=0`.
`language_switch=1` is the **default** and auto-sets language from proxy/IP country [official]
— already matches "locale follows the proxy." Only flip to 0 + set an explicit proxy-country
language if auto-detect gets the country wrong; never hardcode the operator's own locale.

## `fakey` (2FA seed)

Official field, both `create`/`update`: `fakey` [official]. 🔺 Field-observed 2026-09-21: store
**without spaces** — supplier files ship TOTP secrets space-grouped (`XXXX XXXX XXXX`), AdsPower
does not strip them. Strip whitespace before writing.

## Facebook liveness cannot be probed by script — do not build a checker

Field-observed 2026-09-21/22: Facebook returns HTTP 400 to any non-browser client (curl/urllib/
requests) even through a healthy proxy with valid cookies. Likely TLS/client fingerprinting
(JA3-style), not the cookies [unverified mechanism] — a 400 there proves nothing about session
health. Only real test: open the AdsPower profile and watch the live browser session.

## `last_open_time`: telling untouched from used

`last_open_time` is `"0"` until a profile is first opened (field-observed 2026-09-22) — the
reliable way to tell an untouched profile from a used one, and therefore whether its bound proxy
is still clean. Doctrine on what to do with that signal → `01` (proxy lifecycle).

## Proxy reuse

`user_proxy_config` is per-profile, so nothing stops the same exit appearing on many profiles —
and per `01` that is the normal way to run them, not a compromise. Set the exit from a fixed
list by a deterministic rule and move on; there is no used-proxy state for this API to hold and
none worth keeping outside it.

What the API does give you is `last_open_time`: `"0"` means the profile was never launched, so
its exit never reached Facebook at all. Useful when rebuilding a batch — it tells you the
profiles are untouched, not merely untouched-looking.

## Worked examples

`user/create` (v1) — avoids every trap above:

```json
{
  "group_id": "0",
  "domain_name": "facebook.com",
  "open_urls": ["https://business.facebook.com/adsmanager/manage/campaigns"],
  "fingerprint_config": {
    "random_ua": {"ua_system_version": ["Windows 10"]},
    "language_switch": "1"
  },
  "user_proxy_config": {
    "proxy_soft": "other", "proxy_type": "socks5", "proxy_host": "1.2.3.4",
    "proxy_port": "1080", "proxy_user": "user", "proxy_password": "pass"
  },
  "fakey": "ABCD1234EFGH5678"
}
```

`user/update` (v1) — rotate credentials/2FA; fingerprint OS/UA is not changeable here:

```json
{
  "user_id": "kp8x1a2",
  "domain_name": "facebook.com",
  "open_urls": ["https://business.facebook.com/adsmanager/manage/campaigns"],
  "fakey": "ABCD1234EFGH5678"
}
```
