# 13 — Autolaunch SaaS parity: what they do, how, and where it lives here

Reviewed 2026-09-14 (scrape prefixes point at `02`; Power Editor scopes ≠ human UI). 2026-09-02. Sources: vendor sites (cloud.dolphin.tech, cabinet.partners, fbtool.pro),
RU review aggregators (cpa.rip, traffnews, greyhunter, partnerkin, cpa.club), one working
practitioner script (dvygolov gists / YWB.FBLogin). No vendor publishes mechanics; "how" below
is reconstructed and labelled.

## Mechanism

Dolphin Cloud, FBTool, Nooklz, Saint.tools, cabinet.partners are **Graph API wrappers with a
dashboard**. "Autolaunch" = (1) a **bundled session import**: user token scraped from the Ads
Manager browser session (`EAAB…`, regex on `accessToken="` in adsmanager HTML or `window.__accessToken`)
**paired with session cookies** (full browser set incl. `datr`, `sb` — our required subset is
`02` §5), matching User-Agent, and egress
proxy — no developer app or BM admin needed — plus (2) a form UI looping the same create calls over N
accounts. In field testing and vendor documentation (e.g. FBTool guidance on restricted API accounts),
calling `graph.facebook.com` with a standalone `EAAB` token without session cookies and proxy alignment
frequently triggers `OAuthException code 1: Invalid request` (trace `opes_mids`), despite the token
showing `Valid: True` in the Token Debugger. Autolaunch platforms bypass this by attaching the exported
session cookies and matching proxy/UA to Graph calls. Everything marketed as a feature is a documented
endpoint already in `scripts/`, minus a few UI-only actions (end of feature map). [practitioner +
source-code: dvygolov/YWB.FBLogin, cpa.rip token guide, fbtool.pro FAQ "import cookies/access_token";
inferred for cabinet.partners, which discloses nothing]

Why we differ: System User token from your own BM is session-independent, scoped, revocable,
survives persona logout, and needs no browser cookies (`02`). Scraped EAAB is the persona's
session — `META_COOKIES` + `META_PROXY`, death codes in `02` §5, **un-scopeable**: scopes are
the Power Editor app's fixed set, not the human's BM/UI role (live 2026-09-14: no
`catalog_management` on that EAAB). Billing-page **EAAI** and BM-Settings **EAAG** are other
first-party apps, not an upgrade of the Ads Manager token — table in `02` §5. Ban correlation
by pipe mechanism: **unquantified anywhere** [not found]; practitioner consensus blames account
quality/spend velocity, not the pipe. FIELD 2026-09-27 (n=1, cause not proven): on one System User
token the account with the heaviest write load + a throttle retry storm died "automation that doesn't
follow our rules", siblings lived — pacing, not pipe (`02` §8, `16` § Pacing).

## Feature map

| SaaS feature (Dolphin / FBTool / cabinet.partners) | Ours | API |
|---|---|---|
| Import accounts by cookies / token | operator hands System User token + ids (`02` §1) | — |
| Template → N accounts | `metaops bulk-plan` → `bulk-apply` (template × accounts, bound inputs, ACTIVE by default — `create_status: PAUSED` override) | `POST /act_X/campaigns\|adsets\|adcreatives\|ads` |
| Creative-file hygiene | `uniquify.py` (`--no-crop` for text-heavy banners, `--report` prints dHash/pHash distance) changes local bytes only (does not change a content/state-level reject, `07`) — measured 2026-09-03: its jitters move 64-bit dHash 0–6 / pHash ≤6, under the ~8 near-duplicate threshold, and Meta's detector is SSCD; use independently produced source creatives for real variance, then workspace-bound `metaops media` per account | client-side; `POST /adimages`, `/advideos` |
| Catalog/feed/product-set create, batch upsert/delete, instant fetch | `metaops catalog create\|feed create\|set create\|products batch`, `metaops feed sync\|swap` (`16`, `17`; mutating batch/feed actions require literal confirms) | `POST /{business}/owned_product_catalogs`, `/{catalog}/product_feeds`, `/{catalog}/product_sets`, `/{catalog}/items_batch`, `/{feed}/uploads` |
| Distribution "All→All" / "1→1" | spec shape: ads per ad set in template; per-account `media` block | — |
| Duplicate campaign/ad set ×N | `metaops clone campaign\|adset\|ad <id> --times N` (level by level, PAUSED; deleted/archived descendants skipped; `deep_copy` capped at <3 objects; campaign clones count against one-create-per-account-per-~3h, `16` § Pacing) | `POST /{id}/copies` |
| Scheduled launch / dead-hours avoidance | spec `start_time` (ACTIVE `apply` refuses a past one); `metaops activate --refresh-start` for PAUSED builds; `04` → Scheduling | `start_time` |
| Autorules (kill/scale/notify) | `metaops rules ladder/list/history/execute/delete` (Poisson ladder, `--confirm RULES` for pause mode, `EXECUTE` to dry-fire) | `POST /act_X/adrules_library`, `/{rule}/execute`, `/adrules_history` |
| Budget ramp / mass status | `metaops edit status/budget/rename/ramp` (±20% + late-day guard, `--confirm SPEND` to activate/raise, `PAUSE` to stop delivery) | `POST /{id}` |
| Comment auto-hide by trigger words | `metaops comments hide\|delete --matching REGEX --confirm HIDE\|DELETE` (Page token) | `GET /{post}/comments`, `POST /{comment}?is_hidden=true` |
| Spend/status/ban dashboard, Telegram alerts | `metaops monitor --telegram` (verdicts incl. STALL, JSONL, Bot API via `TG_BOT_TOKEN`/`TG_CHAT_ID`) | `GET /act_X?fields=account_status…`, `/insights`, `/ads?fields=effective_status` |
| Rejected-ad review + appeal | `metaops review [--previews]` (ad_review_feedback, issues_info); **appeal is UI-only**; operator rule: on a disapproval do not edit or resubmit | `issues_info` read only |
| Pixel attach to account | `metaops business pixel create/share/shared`, `metaops doctor --attach-pixel`; `business capi test` proves the dataset receives events | `POST /act_X/adspixels`, `POST /{pixel}/shared_accounts` |
| Page avatar/cover/about writes | `metaops page set --avatar/--cover/--about/--website --confirm PAGE`. **Create+rename: UI-only** | `POST /{page}/picture`, `/{page}` |
| Card binding, auto-topup, balance payment | **UI-only** — no billing writes in Marketing API. Agency crypto topup or persona's browser (`03`) | — |
| BM creation, new ad account under BM | BM: UI-only. Ad account: `metaops business adaccount create` (new-BM cap = 1 account, `03`); users/partners: `business user invite\|assign`, `partner share` | partial |
| Tracker cost push (Keitaro/Binom) | `metaops keitaro push` (dry run, then `--confirm PUSH`; key `sub_id_6`, `16` Keitaro, `tracker-ops/01`); Binom has no script | `/insights` |
| Per-creative stats every 15 min, cross-account (≥15 min is the floor on Limited tier, `16` § Pacing) | `metaops insights leaderboard --accounts …` (join on `ad_name` = creative name only within one currency; mixed currencies are rejected); `insights pull --csv` → tracker | `/insights` |
| Team seats/roles | `metaops business user invite --role EMPLOYEE\|ADMIN` | — |
| "AI assistant over your data" (cabinet.partners) | this skill + `insights.py` output | — |
| 2FA/checkpoint handling, warm-up | not an API concept — `01` freeze protocol, antidetect profile | — |

## Their defaults vs ours

No vendor documents attribution/Advantage+/multi-advertiser defaults [not found]; payloads
omit the fields, so Meta's defaults apply: **7d click, every enhancement ON, multi-advertiser
ON**. Quiet reason "same creative performs differently from the tool" — ours pins 1/1/1 by default
(casino Purchase: 7d click / 1d view, set explicitly) and all OPT_OUT (`SKILL.md` § Launch defaults).

## Volume/hygiene practices (practitioner, cpa.rip/partnerkin)

- Caps: ~200 launches/creatives per day per tool tier; >50 launches/day called unmanageable
  even automated — those are per-tool totals across many accounts. Per account: max one new
  campaign create per ~3h (`16` § Pacing, FIELD 2026-09-27). `bulk.py` has no cap — TL sets one.
- One proxy per account from antidetect layer; no vendor publishes inter-call delays [not
  found]. `graph.py` backs off on BUC headers; on a throttle code stop + ≥30 min per-account
  cooldown, no retry loop (`16` § Pacing). Don't sprint `bulk.py` with hundreds of accounts
  on one persona IP — split by persona.
- Warm-up (browsing, small spend before real budgets) is RPA/antidetect territory, not the
  launcher's; `04` → Spend warm-up.

## Open items

- IG comment moderation (`/{ig_media_id}/comments`, `is_hidden`) — add to `comments.py` when a
  funnel needs it.
- Appeal submission, card binding, BM/Page creation stay in the antidetect profile.
- Whether any vendor uses its own developer app rather than scraped tokens: unknown for all.
