# 12 — Meta Ads CLIs

**Agent boundary:** do not use either CLI to write. Route every agent mutation through the
workspace-bound `metaops` command, which supplies the plan/apply/verify/activation gates. This
reference is for a human operator's diagnosis and manual recovery only.

Verified 2026-09-02: the official **`meta-ads` 1.1.0** package is proprietary, ships compiled
wheels without a source distribution, and exposes no public extension interface. It is not an
open-source base to fork. Re-verify on new version: `meta --version`.

The separately named **`meta-ads-cli`** project from Attainment Labs is MIT-licensed and has a
public GitHub repository. It is unrelated to the official package and lacks this project's
plan/apply/verify/activate gates. Do not put either package in the launch authority path.

## Verdict

The official CLI is complementary, not a replacement for `metaops`. **Can** express every launch default we
enforce (raw-JSON escape hatches exist), but no `validate_only`, no read-back diff, no
multi-account run, no resume state, no currency guard, no proxy setting; rides official
`facebook-business` SDK whose video uploader still points at dead
`graph-video.facebook.com` (SDK 26.0.1 `video_uploader.py:363`, issue #701 open). Use for:

| Use | Command | Why it beats a script |
|---|---|---|
| Attach a pixel to an ad account (the 1815045 UI step) | `meta ads dataset connect <PIXEL> --ad-account-id act_X` | one line, no Business Settings clicking (also `metaops doctor --attach-pixel`) |
| Create/list datasets, assign users | `meta ads dataset create/list/assign-user` | — |
| Catalog CRUD incl. product items and sets | `meta ads catalog/product-set/product-item/product-feed …` | product create with `--price --currency --image-url` |
| Quick reads with any field | `meta -o json ads adset get <ID> --fields name,attribution_spec,targeting` | `--fields` is a raw passthrough |
| Insights ad hoc | `meta -o json ads insights get --date-preset last_7d` | — |
| Account-level recommendations | `meta -o json ads guidance list` | UGP "opportunity" suggestions — advisory only (`03`) |
| Lift/split studies | `meta ads study list` | — |
| DCO (dynamic creative) creative from local files | `meta ads creative create --images a.jpg --images b.jpg --titles … --bodies …` + ad set `--dynamic-creative` | our `launch.py` has no DCO kind |

Do **not** use for the launch itself: no dry run, one account/invocation, defaults are Meta's
(Advantage+ on, multi-advertiser inherits account default, attribution inherits 7d click only — no view, FIELD 2026-09-27 — unless
`--attribution-spec` passed).

## Setup

```bash
uv venv -p python3.13 .venv-meta && uv pip install -p .venv-meta/bin/python meta-ads pysocks
export ACCESS_TOKEN=$META_TOKEN AD_ACCOUNT_ID=act_123 BUSINESS_ID=456   # or a .env file
export HTTPS_PROXY=$META_PROXY          # requests honours env proxies; socks5h needs pysocks
.venv-meta/bin/meta auth status
```

Config keys the binary reads: `ACCESS_TOKEN`, `AD_ACCOUNT_ID`, `BUSINESS_ID`, `APP_ID`,
`APP_SECRET` (env, then `.env`, then config file). Python ≥3.12. Global flags:
`-o table|json|plain`, `--no-input`, `--no-color`, `--debug`. Deletes prompt unless `-f`.

## Command surface (1.1.0)

`meta auth status` · `meta ads adaccount list|get|current` · `page list|get` ·
`dataset list|get|create|connect|disconnect|assign-user` · `catalog …` · `product-set …` ·
`product-feed …` · `product-item …` · `campaign list|get|create|update|delete` ·
`adset …` · `ad …` · `creative list|get|create|update|delete` · `insights get` ·
`guidance list` · `study list`.

### Flags that matter for our defaults

| Object | Flag | Notes |
|---|---|---|
| campaign create | `--objective` (ODAX only), `--daily-budget`/`--lifetime-budget` (cents, CBO), `--adset-budget-sharing` (flex), `--bid-strategy`, `--special-ad-categories`, `--spend-cap`, `--start-time/--stop-time`, `--pacing-type`, `--status` (default PAUSED) | budgetless campaign = ABO automatically |
| adset create | `--targeting @file.json` (raw; CLI injects `targeting_automation.advantage_audience` = 0, or 1 with `--advantage-audience`, unless your JSON sets it), `--promoted-object @file.json`, `--attribution-spec '[…]'`, `--dsa-beneficiary/--dsa-payor`, `--incremental-attribution` (mutually exclusive with attribution-spec), `--destination-type`, `--dynamic-creative`, `--pacing-type day_parting`, `--bid-amount`, `--status` (default PAUSED) | `--targeting-countries` is the shortcut; raw JSON replaces it |
| creative create | `--object-story-spec @oss.json`, `--asset-feed-spec @feed.json`, `--degrees-of-freedom-spec @dof.json`, `--contextual-multi-ads/--no-contextual-multi-ads`, `--url-tags`, `--instagram-user-id`, `--product-set-id`, `--image/--video` (local upload), DCO `--images/--videos/--titles/--bodies/--descriptions/--call-to-actions`, `--object-story-id` (boost post), `--authorization-category` | `--no-contextual-multi-ads` = our OPT_OUT; help text wrongly implies "inherit account default" is neutral — the account default is OPT_IN |
| ad create | `--creative-id`, `--pixel-id` (auto tracking_specs), `--tracking-specs '[…]'`, `--conversion-domain`, `--schedule-start-time/--schedule-end-time`, `--status` (default PAUSED) | — |
| any get/list | `--fields a,b,c` | raw passthrough; unknown field = API error |

Update commands are thin (name/status/budget/bid_amount/end_time; creative body/title/media).
No `copies`, no `adrules_library`, no comments, no batch — those stay in `scripts/`.

## Live-verified 2026-09-02 (System User token, own BM)

`auth status` ✓ · `adaccount list` (3 accounts incl. client) ✓ · `dataset list` (shows
`owner_business`) ✓ · `adset list --fields name,attribution_spec` ✓ · `guidance list` → "No
results" fresh account · `study list` → none · `creative create --object-story-spec @oss.json
--degrees-of-freedom-spec @dof.json --no-contextual-multi-ads --status PAUSED` → created;
read-back `contextual_multi_ads = OPT_OUT`, features OPT_OUT, **creative status ACTIVE (flag
ignored)**. No proxy env set (System User); nothing else tried on network.

## Traps

- Video upload via SDK → deprecated host → expect 500s until #701 fixed. Use `media.py` for
  video.
- `--degrees-of-freedom-spec` help lists feature names (`image_brightness_and_contrast`,
  `text_improvements`) **not** in v26.0 `creative_features_spec` reference; use keys in
  `launch.py DEFAULT_OPT_OUT`.
- Creative `--status` defaults ACTIVE on Meta's side — irrelevant for spend (ads PAUSED), but a
  creative entering review the moment it exists is not.
- `--advantage-audience` unset = "API default"; constrained audience → API demands explicit
  value — pass it.
- Confirmation prompts only on `delete`. Nothing asks before `--status ACTIVE`.

Primary sources: [official overview](https://developers.facebook.com/documentation/ads-commerce/ads-ai-connectors/ads-cli/ads-cli-overview),
[official command reference](https://developers.facebook.com/documentation/ads-commerce/ads-ai-connectors/ads-cli/command-reference),
[official PyPI package](https://pypi.org/project/meta-ads/). Separate project:
[Attainment Labs repository](https://github.com/attainmentlabs/meta-ads-cli).
