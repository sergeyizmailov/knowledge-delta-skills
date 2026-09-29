# 00 — Launch runbook (start here for any API launch)

Ordered path "have a token" → "spending". Other files are exception handlers for one step — if a
step passes, move on. Reviewed 2026-09-29; ACTIVE-default 2026-09-25.

`metaops` (`16`) is the only agent-facing Graph write interface; `../scripts/` are internal and
reject direct writes. **Never hand-assemble a Graph payload** — agent writes the JSON spec,
`launch.py` writes API calls. Defaults: `SKILL.md` § Launch defaults. With `workspace.json`:

```bash
metaops --workspace . --profile <name> --json workspace validate
metaops --workspace . --profile <name> --json assets verify --scope core
# Use --scope all when the spec contains any catalog_* creative.
metaops --workspace . --profile <name> --json doctor
```

Receipts (doctor, assets verify): the 24 h TTL now applies only to `apply`, `bulk-apply`, `activate`,
`bulk-activate`; `media`, `edit status`, `verify`, `review`, `insights` still check the binding but ignore
age (`METAOPS_DOCTOR_MAX_AGE_SECONDS` overrides); `assets set-products` also needs a fresh (<24 h)
receipt like `apply`. A DEFINITE failure of `doctor` deletes its receipt; a failed `assets verify` deletes
the same-scope receipt (the core one too on a core failure). A local cooldown, a throttle
(17/613/4/32/80xxx) or an unknown-outcome error does NOT delete a passing receipt. `apply` refuses an
account whose `account_status` != 1; `plan` / `--dry-run` only WARN about it.

```
0 gate  →  1 access  →  2 media  →  3 spec  →  4 dry run  →  7 review layer + 7.5 QA
        →  5 create ACTIVE (one or bulk)  →  6 verify  →  8 activate (create_status: PAUSED runs only)
        →  9 first hour  →  9.5 daily sync  →  9.7 post-approval swap  →  10 kill rules
```

**ACTIVE by default (canonical rule).** `apply`/`bulk-apply` create every object ACTIVE, print
budget in major units + currency, and refuse without literal `--confirm SPEND`. Campaign is built
PAUSED internally and flipped ACTIVE only after the whole tree exists, so a half-built tree never
spends. ACTIVE creates refuse a past/offsetless `start_time` (re-date, re-plan). So steps 7 and
7.5 run BEFORE step 5, and step 6 is a post-hoc check on a spending tree. Top-level
`"create_status": "PAUSED"` restores the old order (create paused → 6/7 → step 8 activate) — use
it whenever a review window before spend is needed (e.g. `9.7` catalog swap).

## Vertical parameters

| Vertical | Gate before spend | Payout event | First optimization event | Playbook |
|---|---|---|---|---|
| iGaming / casino | A&V gambling authorization + per-territory licence, filed **before any ad exists**; 19 markets take no gambling ads | FTD (or qualified FTD) | `COMPLETE_REGISTRATION`, switch to `PURCHASE` at ~20-30 FTD (generic prior; our US PWA team runs `PURCHASE` + bid cap from day one, agreed with the TL 24/09, n=1 read in `casino.md`) | `playbooks/casino.md` |
| Nutra | Health-claim policy | Confirmed COD order | `LEAD` / `PURCHASE` | `playbooks/nutra.md` |
| Crypto / trading | Crypto authorization; exemption boundary decides if there is a path | Qualified reg / deposit | `COMPLETE_REGISTRATION` | `playbooks/crypto-trading.md` |
| News → Telegram | No formal gate; funnel is the risk | Subscribe / bot join | `LEAD` | `playbooks/news-tg.md` |
| Anything else | **`10` Q1/Q2 first** | — | — | shape ports from any playbook |

## 0 — Path exists?

Open `.notes/plan.md` from the `19` template before the first write. `10` Q1 (permission before
spend) / Q2 (no path in any geo); clear the gate in `09` **before any ad object exists**.
Approvals bind to a **specific portfolio + ad account** — a replacement account needs a new one.

## 1 — Access and write probe

Operator hands you, verbatim into gitignored notes: token, ad account id(s), Page id,
pixel/dataset id, tracker campaign URL, proxy (if user token). Token types → `02`.

```bash
export META_TOKEN='...'                               # never on the command line
# user/long-lived token minted in an antidetect profile → same exit IP, always:
export META_PROXY='socks5h://user:pass@host:port'      # when this BM uses a fixed proxy; socks5:// breaks TLS (01)
# Or, only when direct egress from the current IP is intentional for this BM:
export META_ALLOW_NO_PROXY=1
export META_APP_SECRET='...'                          # optional; adds appsecret_proof
metaops --workspace . --json doctor --whoami
metaops --workspace . --profile <name> --json doctor    # PBIA absent = WARN here, but launch.py aborts on it; create it in the UI (18)
```

Exit 0 or don't launch. Gates: token identity · granted scopes (`ads_management`+`ads_read`
required, rest warned) · account in `/me/adaccounts` (assigned, not merely readable) · status +
funding · Page token + PBIA/IG (doctor WARN only since 2026-09-22, but IG is mandatory so
`launch.py` refuses without it, `18`) · **pixel attached to THIS
ad account** (shared to BM ≠ on account, 1815045) · CAPI write · `validate_only` write. A `GET`
proves none of these. Bulk planning validates every selected profile before any build.
Token died / access denied → `02`. Asset not visible → `03`. No proxy: under `metaops` only workspace
`defaults.allow_no_proxy: true` works (an exported `META_ALLOW_NO_PROXY=1` is dropped). Building the BM
itself → `22`.

## 2 — Media

```bash
metaops --workspace . --profile <name> --json media \
  --video creatives/*.mp4 --image creatives/*.jpg
```

Writes `.metaops/media/<profile>.json` (`image_hash`, `video_id`, thumbnail hash), **overwritten
every run** — second set (e.g. white): `--manifest .metaops/media/<profile>-white.json`. Hashes
are **account-scoped**: upload per account; bulk reads the row's `media` block. Mechanics → `04`.

## 3 — Write the spec

Copy nearest `scripts/specs/` example. Put account `"currency": "USD"` in spec (guards a cents
template hitting a TWD/JPY account at 100x).

| `creative.kind` | Shape | Example |
|---|---|---|
| `link_image` | single image link ad | adapt `example-link-video.json` |
| `link_video` | single video; destination in CTA, `video_data` has no `link` | `example-link-video.json` |
| `link_carousel` | 2–10 `cards`, each `image_hash` XOR `video_id`; cards inherit `link` | `example-abo-1-3-1.json` |
| `dlo` | language slots via `asset_feed_spec`; SINGLE_IMAGE/SINGLE_VIDEO only, locale ids NUMERIC, ≥2 rules, one `is_default`, `description`=" " for blank | `example-dlo.json` |
| `catalog_collection` | storefront hero + product set, **≥4 items** (2490457) | `example-catalog-collection-tr.json` |
| `catalog_single` | one-product set → one deep-linked card (`force_single_link`), no minimum | `example-catalog-single.json` |
| `catalog_carousel` | multi-product carousel from the set (no `force_single_link`; Meta picks the card count), no documented minimum; `multi_share_end_card` default false | adapt `example-catalog-single.json` |

**Link ads (longread) copy:** set `headline` (neutral, ≤40 chars, never the casino name), `cta`
(`SEE_DETAILS`: the launch.py default is `LEARN_MORE`; SEE_DETAILS verified live on CF1 ads via API
2026-09-29), `display_link` (empty or root domain; not on `link_video`: no caption field there, error in strict),
`description` empty or neutral, and top-level `"lint": "strict"` (headline >40 / offer or casino words in
headline+description = error; strict also needs non-empty headline and message; body is not linted).
Campaign / ad set / ad names: no casino name (not linted, check by hand). Template:
`scripts/specs/example-us-longread-cbo.json` (US, CBO, bid cap, 7d click / 1d view, `fb_ig_all`,
`advantage_audience: false`, region key placeholder).

**Placements:** set ad set `placements: "fb_ig_all" | "fb_ig_feeds"` (`SKILL.md`), or explicit
`publisher_platforms` + positions (`fb_ig_all` also sets `device_platforms: ["mobile"]`). Omitted = `plan`
WARNING and `verify` WARNING (FAIL under `lint: "strict"`). **Bids:** conversion
goals need a cap; `bid_policy: "require_cap"` makes a missing cap a load error; `daily_min_spend_target` /
`daily_spend_cap` are minor units; `advantage_audience` must be a real bool or 0/1. The `plan` JSON
envelope carries `data.warnings`: read them (uncapped conversion goal, PURCHASE without explicit
`attribution`, omitted `publisher_platforms`, non-active account, lint findings).
Reused campaign (`campaign.id`): ad sets are created PAUSED and each is activated after its ads exist
(state key `adsets_activated`).

All `catalog_*`: `message` default `-----` (a wordy one refused unless `allow_message`), headline /
description default `{{product.name}}` / `{{product.description}}` (any `{{product.*}}` tag accepted,
static text refused unless `allow_static_text`), `swap_to` = target SKU(s) for the post-approval swap,
`product_video: true` keeps `media_type_automation` ON so the items' own videos serve (implied by
`format_option` `single_video`/`collection_video`), `format_option` checked against the v26 enum
(`carousel_images_multi_items` default, `carousel_images_single_item`, `carousel_slideshows`,
`collection_video`, `single_image`, `carousel_ar_effects`; `single_video` guide-only, warned).

Catalog source: Google Sheet pulled by Commerce Manager as scheduled feed (`17`, `sheetfeed`);
swap links/images in the sheet, not via batch API.

- **CBO**: `campaign.daily_budget_minor`, ad sets budget-less. **ABO**: every ad set carries
  `daily_budget_minor` (+ `bid_strategy`, `bid_amount_minor` for COST_CAP/BID_CAP), 1-3-1 =
  `example-abo-1-3-1.json`. Mixed/absent → rejected. **EU/EEA**: `dsa_beneficiary` +
  `dsa_payor` on ad set (`example-eu-dsa.json`).
- **Objective**: `OUTCOME_LEADS` for lead/reg funnels; `OUTCOME_SALES` blocks Lead/Submit
  Application events (2446814). Restricted verticals declare real `special_ad_categories` —
  empty is a violation, not a bypass.
- **Optimization event**: aligned with or upstream of payout (a deep event the account can't
  feed stays learning-limited). Site events: `OFFSITE_CONVERSIONS` + `promoted_object{pixel_id,
  custom_event_type}`; `LEAD_GENERATION` is lead-FORMS only (`04`).
- **`start_time`**: conversions 06:00–08:00 geo-time or 1–2h before evening window, **never
  00:00**; reach/traffic next 00:00 (`04` → Scheduling).
- **Attribution**: `"account_default"` sends nothing; silent spec = code `DEFAULT_ATTRIBUTION`
  1/1/1; `"account_default"` = API default 7d click only, no view (FIELD 2026-09-27); casino Purchase = 7d click / 1d view, set explicitly (`21`, `playbooks/casino.md`).
  **Immutable after create** (1504040) — wrong window = new ad set.
- Catalog creative with video cards: opt `media_type_automation` back in via
  `creative.opt_out_features`.
- **DLO + ODAX** field-confirmed only for `OUTCOME_SALES`+`OFFSITE_CONVERSIONS`+`PURCHASE` and
  `OUTCOME_LEADS`+`OFFSITE_CONVERSIONS`+`COMPLETE_REGISTRATION` (`04`); others unverified and
  invisible to dry run. Test one live DLO ad before a batch.

## 4 — Dry run

```bash
metaops --workspace . --profile <name> --json plan --spec specs/mine.json
metaops --workspace . --json bulk-plan \
  --template specs/mine.json --accounts accounts.json --run <wave>
```

`bulk-plan` has no `--profile` by design: each `accounts.json` row selects its bound profile;
absent/mismatched binding fails. `validate_only` creates nothing; on failure read
`error_data.blame_field_specs`. Campaign+creative validated by Meta now; ad sets/ads locally now,
by Meta right before each real create (`synchronous_ad_review` runs there). Real run refused
without a clean whole-batch dry-run marker. Plan hashes every input — edited input = new plan.

## 5 — Create, ACTIVE by default

```bash
metaops --workspace . --profile <name> --json apply --plan .metaops/plans/<plan>.json --confirm SPEND
metaops --workspace . --json bulk-apply \
  --plan .metaops/plans/<bulk-plan>.json --confirm SPEND --verify [--dlo-tested]
```

- DLO/catalog template on >1 account: `apply` ONE account, verify, then `bulk-apply
  --dlo-tested` (`04` → DLO).
- **Pacing (FIELD 2026-09-27, after an Account Integrity "automation" disable on the most
  API-loaded account, `06`):** ≤1 new campaign create per ad account per ~3h; exactly one
  read-back after create, no polling loops; code 17/4/32/613 → stop, ≥30 min cooldown for that
  account, never sleep-and-retry (Limited tier ≈300 calls/h/account, `04`). Weak/new account:
  open below target budget, consider the first launch in Ads Manager UI.
- State `.metaops/<run_id>.json` marks each create in-flight **before** the POST. Dropped
  connection → never retried (may have applied); next run asks to reconcile. `graph.py` retries transient
  errors only for GETs and `idempotent=True` calls; a non-idempotent create raises once with
  `outcome_unknown=true` (`graph_error` reports the LAST error, int `code`). Every Graph path is validated
  first (`.`, `..`, empty segments, `% ? # \`, whitespace/control characters are rejected). Graph *rejection*
  clears the marker, retryable. Resume = the same `apply`; if the spec `start_time` has passed
  meanwhile, add `--refresh-start <future ISO>` (re-dates only missing ad sets; no new plan). No
  `--rollback`: pause (`edit status --confirm PAUSE`); `--status DELETED --confirm DELETE` removes any object, spend included (insights stay in account reports).
- Bulk: substitutes account/page/pixel/IG per row, expands `{tag}` in names (naming contract: `03`;
  no casino names), deep-merges `overrides`, per-account `media`
  (keys `"<adset index>:<expanded ad name>"` or `"<expanded ad name>"`; misses and shared names are
  warned; the media manifest is merged, not overwritten),
  resolved specs in `.metaops/bulk/<run>/`, own state per account. One failure doesn't stop the
  rest. Re-run resumes, never duplicates.

## 6 — Verify before you trust it

```bash
metaops --workspace . --profile <name> --json verify --plan .metaops/plans/<plan>.json
```

Fails (no receipt) on any `in_flight` key (outcome unknown — e.g. bare 503 on creative POST;
only Ads Manager can tell) or any spec ad set/ad missing from `objects`. Reconcile, re-run
`apply --plan … --confirm SPEND` — creates only what's missing.

Diffs read-back: ad set/ad `status`, DLO rules/locales/text, budget in minor units (campaign
under CBO, ad set under ABO), bid strategy, optimization goal, promoted object, targeting,
**attribution_spec**, **DSA fields**, destination per kind, **display link**
(`object_story_spec.link_data.caption`; MCP `display_link`, `15`), description, `conversion_domain`
(verify.py diffs these since 2026-09-29; before that it did NOT diff caption, despite this section),
`template_url_spec`, **`contextual_multi_ads` = OPT_OUT**, **no OPT_IN in `degrees_of_freedom_spec` or
`creative_sourcing_spec` unless `creative.opt_in_features` lists it**, **`publisher_platforms`**
(FAILS if a pinned platform is missing or AN / Messenger / Threads appear that the spec did not list;
positions are compared only when the spec/preset listed them; a spec that never pinned placements
only WARNS unless `lint: "strict"`) and **`instagram_user_id` on every ad**, every `effective_status`.
Booleans compare as true/false/1/0. Graph silently ignores unknown JSON keys and fills enum defaults. MCP-created objects (`02` §6) never passed `verify` — diff them here too.

Run immediately after ACTIVE create; on mismatch pause the tree first (`edit status --ids …
--status PAUSED --confirm PAUSE`), diagnose second (`00` §9).

UI must prove, **before it spends**: Multi-advertiser checkbox on FORMAT_AUTOMATION collection
creatives (not readable via API), placement previews (4:5 feeds, 9:16 Stories/Reels).

## 7 — Review layer (only if funnel needs one)

`07` — filter stack, white-page requirements, LIVE/DEAD/SPLIT. Must be live BEFORE `apply`
(ACTIVE default). Cloak stays **off** until the ad is serving. Product-set repair: `04` →
Collection/catalog quirks, via `metaops assets set-products`. PWA builders → `11`.

## 7.5 — Final QA gate (before spend)

All before `apply --confirm SPEND` (under the PAUSED override: before `activate`):

- Preview every ad (crop/enhance, §6). Allowed after create: ad doesn't deliver until review
  approves (`effective_status`, minutes per `19`) — pause in that window if wrong.
- One real click through redirect → Keitaro → event fire (`senior-buyer-ops/03`).
- Naming matches tracking plan — wrong name breaks tracker split silently
  (`senior-buyer-ops/SKILL.md` contract #6, `tracker-ops/03`).
- Domain/SSL and macros re-verified (`senior-buyer-ops/03`; `07`). The display link itself is diffed
  by `verify` now, but whether it names the casino is a human check.
- Final IDs, URLs, subs, settings written to `.notes/`.

## 8 — Activate (create_status: PAUSED runs only)

Re-activating anything paused later is `edit status --ids … --status ACTIVE --confirm SPEND`,
not `activate`.

```bash
metaops --workspace . --profile <name> --json activate \
  --plan .metaops/plans/<plan>.json --confirm-ui REVIEWED --confirm SPEND \
  --refresh-start 2026-09-03T07:00:00+03:00

# For a bulk plan, activate exactly one reviewed account per command:
metaops --workspace . --profile <name> --json bulk-activate \
  --plan .metaops/plans/<bulk-plan>.json --account act_123 \
  --confirm-ui REVIEWED --confirm SPEND \
  --refresh-start 2026-09-03T07:00:00+03:00
```

No activate-all. A past `start_time` doesn't error — it starts immediately in dead hours, so
refresh it. `--refresh-start` records `start_overrides` in the state: re-run `verify` before a
second `activate`. Ads/ad sets first, campaign last; stops on first failure. Confirm with operator:
budget in **major units + currency**, schedule, destination, creatives, UI multi-advertiser
check, `verify` exit 0 on this exact state (`<state>.verified.json` holds state + spec hash;
refused if state changed, receipt made without `--spec`, or different spec).

## 9 — First hour

- Insights empty 15–40 min on fresh campaigns — not a delivery failure.
- Check `effective_status`, spend, destination, tracker receipt, billing.
- No spend, no error: future `start_time`, review pending, billing hold, spend cap — verify
  before touching (`05`).
- Rejected ad cannot be enabled (2490468) — switch it off; a new ad needs a different
  creative/angle/PWA. Never re-upload the rejected one into the same account (reads as
  circumvention, FIELD 2026-09-27). **Operator rule: on a disapproval do not edit or resubmit.**
  Several ads going DISAPPROVED ("Spam") within minutes of approval, or an account-level notice → `23`.
- `account_status` 3 / "Payment needed" = billing, not a ban; clears once the card charges.
  `balance` = unbilled amount in cents, not prepaid money (FIELD 2026-09-27).
- **Budget/billing anomaly: pause first, diagnose second** (2026: a 100x budget kept spending
  while units were debated).

## 9.1 — Operate

```bash
metaops … review --state .metaops/run.json            # ad_review_feedback / issues_info; exit 1 on rejects
metaops … review --tree                               # campaign > ad sets > ads in one read (status, budget, bid, attribution, targeting, feedback)
metaops … monitor --accounts accounts.json --telegram   # status + spend sweep, STALL (≥40 impr, 0 clicks), survival log, TG alerts
metaops … rules ladder --target-minor 1200 --event … --level ADSET --mode pause --ids … --confirm RULES   # pause mode needs --ids or --all-adsets
metaops … edit budget --ids … --budget-pct +20 --confirm SPEND · edit status --ids … --status PAUSED --confirm PAUSE · clone campaign <id> --times 2   # --times N: 3 h create pacing
metaops … edit rename --set ID=NAME · edit bid --bid-minor N --confirm BID · edit schedule --end-time ISO+offset --confirm SCHEDULE   # full list and review effects: 16
metaops … comments hide --all --matching "scam|fake" --confirm HIDE
metaops … insights pull --level ad --date-preset yesterday --csv day.csv · insights leaderboard --accounts accounts.json
metaops … insights fatigue --event offsite_conversion.fb_pixel_lead   # weekly per-ad creative-fatigue sweep (meta-ads/08 §10), notify only
```

UI-only: appeals (appeal-or-replace is the TL/agency's call, `05`), billing (the billing threshold can be
neither read nor set via API, UI only), BM/Page creation. Ladder math → `senior-buyer-ops/04`.
A `monitor` sweep that hits a GraphError adds an `ERROR` verdict and exits non-zero.

## 9.5 — Daily sync

```bash
metaops --workspace . --profile <name> --json insights pull \
  --level ad --date-preset yesterday --csv .metaops/day.csv
```

Rows in account timezone (`date_preset=yesterday` = the account's yesterday). `insights pull` defaults to
1d click / 1d view, not the 7d-click window casino ad sets optimise on. To read the ad set's own window,
look at `attribution_spec` in `metaops review --tree` (CLICK_THROUGH / VIEW_THROUGH days; null = account
default) and pass it: `--action-attribution-windows 7d_click,1d_view` (7d/28d view were dropped 2026-01-12,
refused locally). Placement / geo splits: `--breakdown … --time-increment all_days` (`16` Inspect, `25`).
FB conversions stay indicative; spend, which is what the cost push uses, is window-independent. Push spend as cost to tracker (`tracker-ops/01` Cost push: account currency and
account tz as-is; key on `ad_campaign_id` / `sub_id_6`, not names; a day with spend but no clicks stores
nothing; CPA-auto cost model adds fake cost) — no push = no CPL. **`metaops keitaro push`** does it (dry run by default, `--confirm PUSH` writes; `16` Keitaro): per ad and day, key `sub_id_6`,
account tz and currency, trailing 3 days re-pushed; `keitaro report` joins spend with regs/deps per ad. Dry-run it first, read the
no-click and delta flags, then push.

## 9.7 — Post-approval swap (catalog/creative funnels)

Skipped silently: nothing errors, white set keeps delivering. **Swap each set the moment its ads
are approved; never wait for first delivery** (operator 2026-09-26: every white impression is wasted
spend). Put the target SKU in the spec (`creative.swap_to`); `plan` checks it,
`apply` prints the map. Right after `apply`, start `metaops assets swap --map a1=SKU1,b1=SKU2 --watch
--confirm SWAP` in the background: one verdict per set, a reject or review on another set never holds it, text gate
(product macros + neutral primary text) and target-item gate included (`16`). Pick the path by how
the white→target change is made:

| strategy | swap with | gate |
|---|---|---|
| one white product per set (`catalog_single`, the operator standard) | `assets swap --map a1=T01` | ads on that set |
| several products per set (carousel / collection ≥ 4) | `assets swap --map a1=T01+T02+T03+T04` | same + COLLECTION min 4 |
| same retailer ids, item content replaced (sheet feed) | `feed swap --confirm FEED` | ads on sets holding those ids + rule-based sets |
| same, API catalog | `catalog products batch --method UPDATE --confirm BATCH` | same as feed swap |
| back to white (review request, creative edit) | `assets swap --map a1=W01 --revert` | none (white is safe) |

Ad set can't be repointed (`04`). A catalog shared by ads in ANOTHER account is invisible to the
gate: swap only when those ads are out of review too.
Read back `product_count`, the filter, live card, every ad's `effective_status`. Cloaker ON only
here, filter matching ad-set device/OS + GEO (`senior-buyer-ops/03`; filter stack `07`).

## 10 — Kill rules, agreed in writing

Spend-without-lead cap, CPL cap, account verdict threshold — with TL, before launch, via
`metaops rules` (§9.1). Judge accounts after $30–50 (`SKILL.md` §Non-negotiables), cohorts on
click date (`tracker-ops/03`); small-sample math → `senior-buyer-ops/04`.

## When a step fails

| Symptom | Go to |
|---|---|
| Any API error code | `meta-ads/14` for cause+fix, then `05` for survival response |
| Token died / 190, scopes missing, "not visible to token" | `02` |
| Asset shared to BM but absent on account | `03` (pixel/page assignment) |
| Account restricted, checkpoint, session killed | `01` freeze protocol |
| Account DISABLED, or ads "Spam"-rejected right after approval | `23` |
| Launching by hand in Ads Manager | `24` |
| Which placements to keep | `25` |
| Rejected creative, review not passing | `07` (operator rule: switch off, no edit, no resubmit) |
| Vertical seems to have no path | `10` |
| Verification/authorization demanded | `09` |
| Spec rejected locally (budget mode, advantage_audience, DSA, currency) | message names the fix; shapes in `scripts/specs/` |
| Numbers disagree with tracker | `tracker-ops` metric rule |
| Is this difference even real | `measurement-experimentation-ops` |
