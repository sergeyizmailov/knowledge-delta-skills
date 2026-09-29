---
name: meta-grey-ops
description: "Launches and operates Meta (FB/IG) ads through the Marketing API / metaops CLI: bulk launch (apply creates ACTIVE and spends; create_status PAUSED opt-out), DLO language slots, edit/clone/rules, catalog, MCP vs API access, agency and verification handling, per-vertical playbooks, plus grey-market survival (antidetect/proxy hygiene, cloaking/review-layer). Triggers: 'launch FB ads via API', 'bulk launch on N accounts', 'ad rejected Online Gambling'. Clean theory is meta-ads; tracker metrics are tracker-ops."
---

# Meta Grey Ops

Reviewed 2026-09-29 (docs synced to the 29/09 code fixes; a few sections still carry their own older dates); ACTIVE-default change 2026-09-25. Baseline 2026-09-03 (Sonnet 5 blind): bulk-launch task [K] — shared BM pixel still needs per-account attach (1815045). Launch/operate via API on your own token (= autolaunch SaaS without UI, `13`) + grey survival. "buy well" → `meta-ads` · "count & sync" → `tracker-ops` · "portfolio decisions" → `senior-buyer-ops`.

## Start here

| You are… | Read | Then |
|---|---|---|
| In a directory with `workspace.json` | `references/16-metaops-agent-cli.md` | use `metaops --workspace … --json`; before `apply --confirm SPEND` also read `00` §6–7.5 (§8 only for create_status: PAUSED) |
| Handed a token / asked to launch anything via API | `references/00-launch-runbook.md` | create a workspace in a project dir outside the skill (`scripts/specs/example-workspace.json`), validate it, then use `metaops` |
| Setting up access, deciding MCP vs API, minting/handing over a token | `references/02-access-tokens-and-mcp.md` | come back to `00` |
| Hit an error, a gate, a rejection, a dead token | `00` § "When a step fails" | the one file it names |
| Ad account disabled, or ads "Spam"-rejected right after approval | `references/23-disabled-account-triage.md` | `05`, `03` |
| Launching by hand in Ads Manager (API path not usable) | `references/24-manual-launch-ads-manager.md` | — |
| Own BM from scratch, or a new account after a ban | `references/22-own-bm-from-scratch.md` · `references/26-new-account-after-ban.md` | `02`, `03` |

**Agent writes a JSON spec; `metaops` controls the lifecycle; `launch.py` writes Graph
payloads.** Never hand-assemble a payload or invoke a low-level Graph mutation directly.
New shape → extend `metaops`/the implementation and its tests.

## Launch defaults (what every ad set/ad gets unless the spec says otherwise)

| Setting | Default | Enforced by | Override |
|---|---|---|---|
| Object status at create | `ACTIVE`, all levels — `apply`/`bulk-apply` spend the moment the create succeeds, so both refuse without literal `--confirm SPEND` | internal launcher (`launch.py` `spec["create_status"]`) | `"create_status": "PAUSED"` at spec top level — paused build, activate separately via `metaops activate --confirm-ui REVIEWED --confirm SPEND`. Default path builds the campaign PAUSED internally and flips it ACTIVE only after the whole tree exists — a half-built tree never spends |
| Attribution | 1d click / 1d engaged-view / 1d view on conversion goals; **1d click only** on LINK_CLICKS/REACH/etc. (Meta rejects view windows there, 1885501). Set at CREATE (immutable after, 1504040). **Vertical overrides: casino Purchase = 7d click / 1d view** (`playbooks/casino.md`); market defaults by vertical → `references/21` | `launch.py` `DEFAULT_ATTRIBUTION`; `verify.py` reads it back; `plan` WARNS on PURCHASE without explicit `attribution` (default 1/1/1 is not the casino window) | `attribution: {...}` or `"account_default"` |
| Advantage+ creative enhancements | every feature `OPT_OUT` incl. `adapt_to_placement`; music via `audios: []`. **Ads Manager-built creatives are different** (field 2026-09-29, all five CF1 ads): `creative_sourcing_spec.featured_offering_spec` ("Show spotlights", pulls website text into the ad) reads back OPT_IN while `degrees_of_freedom_spec` shows nothing OPT_IN, and social-feedback preservation is on; API-built creatives read back OPT_OUT | `launch.py` `DEFAULT_OPT_OUT`; `verify.py` flags any `OPT_IN` in `degrees_of_freedom_spec` AND in `creative_sourcing_spec` unless `creative.opt_in_features` lists it | `creative.opt_out_features`; on a live/manual ad only `edit creative --enhancements-off` (`16`) |
| Multi-advertiser ads | `contextual_multi_ads: OPT_OUT` on every creative (Meta Ads MCP cannot set it — its creatives inherit OPT_IN) | `launch.py`; readable on link/template creatives, **UI check before spend** (immediately after create by default, or while PAUSED under the `create_status` override) on FORMAT_AUTOMATION collections | `creative.multi_advertiser: true` |
| Advantage+ audience | must be explicit `true/false` in `targeting`; **`true` caps `age_min` at 25 and forces `age_max` 65** — any hard age/gender requirement means `false` (`04`) | spec rejected without it (v23+ Graph rule) | — |
| Placements | Ad set `placements`: `"fb_ig_all"` (Facebook + Instagram, explicit positions, `device_platforms: ["mobile"]` since story/reels positions are mobile-only; no Messenger / Audience Network / Threads) or `"fb_ig_feeds"` (FB feed + IG stream); explicit `publisher_platforms` + positions win. Omitted `publisher_platforms` = Meta's all-placements incl. AN / Messenger / Threads: `plan` WARNS, and `verify` WARNS on a spec that never pinned placements (FAILS only under `lint: "strict"`). Recipe and when to narrow → `playbooks/casino.md`, `references/25` | **Instagram is mandatory**: `launch.py` rejects any `publisher_platforms` without `instagram`; positions for an untargeted platform or an empty positions list are spec errors; `verify` FAILS `publisher_platforms` the spec pinned but the read-back lacks, AN / Messenger / Threads on the read-back that the spec did not list, and an ad without `instagram_user_id`; positions are required on the read-back only when the spec/preset listed them | positions may narrow, never drop IG |
| Bid policy | conversion goals should carry a cap; `"bid_policy": "require_cap"` (campaign or ad set) makes a missing cap strategy / `bid_amount_minor` a load-time error; `campaign.bid_amount_minor` is rejected (cap lives on ad sets, 1815857) | `launch.py`; `plan` WARNS on an uncapped conversion goal without it | — |
| Link-ad copy (longread) | `headline` = short NEUTRAL line, ≤40 chars (e.g. "Read before you judge"), never the casino/brand name; no offer wording in headline/description; `cta: "SEE_DETAILS"` (launch.py default is `LEARN_MORE`: set it); `display_link` empty or the root domain, never the casino subdomain; `description` empty or neutral. Names of campaign / ad set / ad carry no casino name (own BM, operator 29/09). Body = first-person story, may mention the bonus | top-level `"lint": "strict"\|"warn"`: headline >40 chars and offer/casino words (flagged: welcome bonus, get exclusive, offer valid, valid until, play online, free spins, deposit match, "$N … bonus", casino, jackpot; bare "exclusive" and "claim" are NOT flagged) in headline/description = error in strict, warning otherwise; strict also requires non-empty headline and message; `display_link` on `link_video` = error in strict. The message body is never linted. **Not linted: casino names in campaign/ad set/ad names, and the display_link value: check by hand** | `lint: "warn"` (default) |
| Budget mode | CBO (`campaign.daily_budget_minor`) **or** ABO (every `adsets[].daily_budget_minor`) | spec rejected if both/neither; cap strategies (`COST_CAP`/`LOWEST_COST_WITH_BID_CAP`) need `bid_amount_minor` on every ad set — under ABO that's the ad set's own `bid_strategy`, under CBO it's `campaign.bid_strategy` but the cap amount still lives on each ad set (1815857) | — |
| API pacing | throttle (17/613/4/32/80xxx) is **never retried**: account (or all, for 4/32) goes on a ≥30 min cooldown that every later process honours; one new campaign per ad account per 3 h (also `clone campaign --times N`: stops within the gap); `assets swap --interval` floor 300 s; transient errors are retried only for GETs and `idempotent=True` calls, a non-idempotent create raises once with `outcome_unknown=true`; `x-fb-ads-insights-throttle` is read like the other usage headers (pause at 85%) | `graph.py` (`~/.metaops/pacing.json`, per-process tmp + flock), `launch.py`; `metaops pace` shows state | `METAOPS_PACE_OVERRIDE=1` only to stop spend or when the operator asks |
| Budget unit | integer minor units; **whole units on no-offset currencies (TWD, JPY, KRW, HUF…)** | `launch.py` prints every budget in major units and fails on `spec.currency` ≠ account currency | put `currency` in the spec |
| `start_time` | conversions 06:00–08:00 geo-time, never 00:00; reach/traffic next 00:00 | spec required; `apply` refuses a past or offsetless `start_time` on ACTIVE creates (re-date spec, re-plan); `--refresh-start` exists only on `activate` | — |
| Identity | Page + PBIA (`instagram_user_id: "auto"`) | launcher resolves it. No PBIA: `doctor` only WARNS, `launch.py` aborts (IG is mandatory). `POST /{page_id}/page_backed_instagram_accounts` is deprecated for all versions since 2025-04-21 (v22.0 changelog, verified 2026-09-29; returns #10), and the GET edge is dead: Ads Manager → ad draft → Identity → **Use Facebook Page**, discard draft (`18`) | explicit id |
| EU/EEA geo | `dsa_beneficiary` + `dsa_payor` required | spec rejected without them | — |
| Swap timing | swap each set the moment ITS ads are approved (ACTIVE); never wait for first delivery, white must not spend (operator 2026-09-26). Start `assets swap --watch` right after `apply` | `swapgate.py`: per-set verdicts, other sets' rejects/reviews and zero impressions never block; same gate on `feed swap` / `catalog products batch` / `set-products` | `--revert` (to white), `--paused-ok`, `--force` on feed/batch |
| Catalog text model | texts live in the CATALOG ITEMS (white item = what review reads, target item = what runs); creative carries only `{{product.*}}` tags + `-----`; never target wording in the creative | `plan` checks white items (filled, no gambling words) and target SKUs; `verify` diffs the card texts | `allow_white_text` |
| Catalog texts (swap-safe) | `message` `-----`; headline/description `{{product.name}}`/`{{product.description}}` (else Meta scrapes the link's `<title>`) | `launch.py` refuses wordy message / static headline; `assets swap` refuses ads without macros | `creative.allow_message` / `allow_static_text` |
| Tracking | spec-level `url_tags` inherited by every ad; catalog cards need `template_url` | `launch.py`; `verify.py` diffs destination per creative kind | per-creative `url_tags` |
| Special ad categories | must be declared explicitly (`[]` or the real one) | spec rejected if absent | — |

Not in the scripts and therefore on you: account-level "test new optimizations" enrollment
(Advertising Settings, UI only), billing/card binding, appeals, BM and Page creation.

## Non-negotiables (always apply)

1. **One identity = one egress profile.** Browser, API, and token operations use the BM/operator's
   assigned IP or proxy. Token type does not waive this rule. Scripts refuse to run without
   `META_PROXY` unless `META_ALLOW_NO_PROXY=1` deliberately confirms that direct egress from the
   current IP is expected for this BM (`01`, `02`). **Under `metaops` the only way to run without a
   proxy is `workspace.json` `defaults.allow_no_proxy: true`; an exported `META_ALLOW_NO_PROXY=1` is
   dropped.** Field 2026-09-29: a scraped EAAB from a Mac with no proxy passed `metaops doctor`
   (14 ok, incl. `validate_only`): it works, which is not proof direct egress is safe; per-BM decision.
2. **Cookies gate only the scraped EAAB browser token** (`c_user`/`xs` + proxy/UA, `02` §5) — a
   dev-app or System User token needs none; supplying them elsewhere is inert, omitting them on
   EAAB fails every call with `code 1`. Rule 1's egress default still covers all three: an
   unfamiliar IP can checkpoint the BM mid-flight regardless of token type.
3. **A token rides a login session.** Logout / password change / security rotation kills every
   token minted from it, 60-day included. System User tokens are session-independent — prefer
   them when the BM is yours (`02`).
4. **Restriction / checkpoint = FREEZE.** No re-logins, token regen, profile edits (`01`).
5. **Never touch a work identity from a personal browser or IP.**
6. **Judge accounts after $30–50 spend, not the first hours.** Keep a replacement reserve (`03`).
7. **Bulk = one creative per account.** Identical creative across accounts overheats your own
   auction; `bulk.py` warns, you decide (`03`).
8. **A launch runs on a plan file, not memory.** Copy `19`'s template to `.notes/plan.md` before
   the first write; tick only against a read-back. A todo list forgets steps that fire days
   later — above all the post-approval swap (`00` 9.7) — so the white set keeps spending, no
   error anywhere.
9. **Pace the API like a human operator** (FIELD 2026-09-27: the heaviest-load account, with a
   code-17 retry storm, was disabled for Account Integrity "automation"; siblings on the same token
   lived). One campaign create per account per 3 h, one read-back after create (no polling loops — the only sanctioned poll is `assets swap --watch`
   at ≥300 s, one per account),
   stop on any throttle and leave that account alone ≥30 min, weak/new accounts (tiny lifetime
   spend, low billing threshold) start below target budget. Never re-upload a rejected creative /
   angle / PWA into the same account — switch the ad off. Enforced in code (`metaops pace`).
10. **Operator rule: on a disapproval do not edit or resubmit.** Switch the ad off, leave it, report
    (`references/23`). `edit tags|creative` skips DISAPPROVED / `ad_review_feedback` ads unless
    `--allow-disapproved`: do not pass it. Clean-lane advice to "fix, appeal, resubmit"
    (`meta-ads/07`, `14`, vendor recipes in `04`/`07`) does not apply on this BM.
11. **Own BM: no casino names in campaign / ad set / ad names, headline, description or display
    link** (operator 29/09; the tr-1 launch carried a casino name in campaign name and headline and
    the account was disabled: correlation, cause unproven). `lint` covers headline/description
    only; names and display link are checked by hand.

## References

| Need | Reference |
|---|---|
| **Ordered launch path — START HERE** | `references/00-launch-runbook.md` |
| **Launch plan file** — template copied to `.notes/plan.md`, ticked step by step, carries the deferred swap | `references/19-launch-plan.md` |
| Antidetect, proxies, IP/session discipline, checkpoints, domain/pixel rotation | `references/01-infra-and-identity.md` |
| **AdsPower Local API**: profile create/update payloads, v1/v2 `domain_name` vs `platform` trap, `open_urls` false-ban signal, desktop fingerprint pinning, why cookie liveness can't be scripted | `references/20-adspower-local-api.md` |
| **Attribution market defaults**: window by vertical (casino Purchase vs reg, nutra, lead gen, e-com), All vs First conversion, Meta 2025-26 changes, tracker reconciliation | `references/21-attribution-market-defaults.md` |
| **Access: app use cases, scopes, one app + token per BM (multi-BM rule), System User vs user token, token death, MCP vs API vs CLI, operator handoff checklist** | `references/02-access-tokens-and-mcp.md` |
| Agency setups, BMs, asset sharing, BM-ban recovery, **bought aged "spend" accounts: pre-buy QC + card-before-BM binding order**, billing gotchas, naming, replacements | `references/03-agency-accounts-and-bm.md` |
| Why the scripts do what they do: structures, params, bid strategies, scheduling, DLO, catalog quirks, media, warm-up, re-moderation | `references/04-mass-launch-api.md` |
| API errors — grey survival response (freeze/replace/rotate); canonical code→fix is `meta-ads/14` | `references/05-api-error-catalog.md` |
| Why accounts die, attributed: hazard-rate forensics, balanced infra tests | `references/06-portfolio-forensics.md` |
| Review-layer filters, cloaking, DLO/catalog/unicode/CTM tricks, BM verification (vendor tool configs & unverified hypotheses → `references/07a-vendor-recipes.md`) | `references/07-review-layer-and-cloaking.md` |
| Location fees, tz/currency 60d lock, sanctioned targeting, WABA | `references/08-geo-fees-and-waba.md` |
| Verification gates: business / beneficial-owner / identity, gambling+crypto+financial authorization, order | `references/09-verification-gates.md` |
| **Does this vertical have a path at all** — permission-before-spend and no-path lists | `references/10-no-path-and-permissions.md` |
| PWA funnel builders: join macros, postbacks, CAPI, QA gates | `references/11-pwa-funnel-builders.md` |
| **Meta Ads CLI** (`pip install meta-ads`): what it can do, flags, traps — read before reaching for it | `references/12-meta-ads-cli.md` |
| **Autolaunch parity**: what Dolphin Cloud / FBTool / cabinet.partners do, how (EAAB tokens), feature → our script or UI-only | `references/13-autolaunch-parity.md` |
| Canonical Graph error codes and fixes (not a local reference 14) | `meta-ads/14` |
| Meta Ads MCP live tool inventory (106 tools, params) | `references/15-mcp-tools-live.md` |
| **Agent launcher**: plan/apply/verify/activate contract, JSON output, locks. Also: `edit ... --validate-only` (Meta checks a change, nothing applied), `review --tree`, `activity`, `images list`, `insights pull --breakdown`, `doctor --risk`, `token import`, `keitaro push/report` (FB spend to Keitaro) | `references/16-metaops-agent-cli.md` |
| **Catalog as one Google Sheet** — service-account setup, Commerce Manager scheduled feed, columns, `sheetfeed` | `references/17-catalog-via-google-sheets.md` |
| **Fanpage by GEO/tier**: white vs mechanic vs empty (disputed), name/avatar freeze, one Page vs many, NPE partner-share, PBIA | `references/18-fanpage-lifecycle-and-shielding.md` |
| **Own BM from scratch**: system user, app, pixel + CAPI, sharing, Page/IG, billing | `references/22-own-bm-from-scratch.md` |
| **Disabled ad account / "Spam" right after approval**: what to read, what not to do | `references/23-disabled-account-triage.md` |
| **Manual launch in Ads Manager**: 1-5-1 checklist, Advantage+ sales limits | `references/24-manual-launch-ads-manager.md` |
| **Reading placement performance**: which placements to keep | `references/25-placement-performance.md` |
| **New account after a ban**: minimal footprint | `references/26-new-account-after-ban.md` |
| Per-vertical playbooks (casino, nutra, crypto-trading, news-tg) | `playbooks/` — numbers are dated vendor/team priors, replace with live data |

Declared gaps: no dating or loans playbook; `APP_PROMOTION` only directional in `playbooks/casino.md`.

## Implementation boundary

`metaops` is the only agent write boundary: it rejects workspaces inside the skill directory and
owns command syntax in `references/16-metaops-agent-cli.md`. Low-level scripts are internal; their
POST/DELETE calls run only through a validated, workspace-bound `metaops` process. Generated files
belong in the project workspace. Run `16`'s isolated checks after an implementation change.

Token classes (FB Helper extension, all five supported, `tokens.py`, capability matrix in `02` §5): `META_TOKEN` = ads (EAAB, or System User / own-app user token); optional `META_TOKEN_BUSINESS` (EAAG), `META_TOKEN_CATALOG` (EAAH), `META_TOKEN_EVENTS` (EAAd), `META_TOKEN_RULES` (EAAI), cookies shared in `META_COOKIES`. `metaops token import` files a pasted extension block by class; `doctor` prints the table. Field 29/09: all five read the ad account, EAAd cannot read an ad set (#10).

Graph quirk (field 29/09, CF1): per-parent edges `{adset}/ads`, `{campaign}/ads` and nested `adsets{ads{}}` can answer EMPTY while `act_ID/ads` lists the ads; read the flat account edge (with `filtering` on `adset.id` / `campaign.id`).

Env: `META_TOKEN` (required; any token kind — System User, your own app's user token, a
third-party dev app's user token, or a scraped browser token, `02` — `workspace.json`'s
`profiles.<p>.token_kind` tells `assets verify` which BM-ownership checks it can hard-gate vs.
only warn on), `META_PROXY` or (direct scripts only) `META_ALLOW_NO_PROXY=1`; under `metaops` use workspace
`defaults.allow_no_proxy`, optional `META_COOKIES`
(scraped EAAB only), `META_USER_AGENT`, optional `META_APP_SECRET` (`appsecret_proof`),
`META_API_VERSION` (pinned `v26.0`; must look like `vNN.N`, a warning outside v25/v26), `GSHEETS_JSON_KEY_FILE` (sheetfeed / feed swap),
`TG_BOT_TOKEN`+`TG_CHAT_ID` (`monitor --telegram`). Never pass a token on argv.
