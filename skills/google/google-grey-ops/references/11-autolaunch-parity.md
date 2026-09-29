# 11 — Autolaunch / mass-account tooling on Google: what exists, what does not

Reviewed 2026-09-02. Sources: vendor sites and RU/EN arbitrage blogs (afftimes, traffnews,
conversion.im, piratecpa, cpa.rip), vendor account shops (invcc, gmcshop, okayfy,
buydigitalaccount), official Google docs for the negative claims. Every vendor number is a
vendor claim.

## The market shape (why the Meta playbook does not port)

- **No Dolphin Cloud / FBTool-class Google launcher exists.** Nothing found that takes N accounts
  plus a template and mass-creates campaigns through the Ads API. Closest: **Noogle** (automation on
  top of Octo Browser: registration, farming, ban-recovery) — browser RPA, not API, blog-sourced
  only.
- Google Ads Scripts can't create campaigns/accounts from nothing (official); Google Ads Editor
  isn't agent-drivable. So every "автозалив Google" product is antidetect-browser automation of
  the UI, not a Graph-style token pipe. The Meta mechanism (scraped session token → API loop) has
  no Google analogue — the Ads API needs a **developer token issued to an MCC**, so the supply
  problem moves from "session" to "MCC + developer token + billing identity" (`01`, `02`).
- What's farmed instead: **accounts**, sold with the browser profile. Ads-account farming guide
  (afftimes, RU): antidetect **AdsPower / AntBrowser** recommended, Dolphin{anty} discouraged for
  Google ("Google sees hardware better") — contradicted by traffnews' Dolphin review; residential
  IPv4, never mobile proxies ("Google is very triggered by IP changes"); ~14 days of warm-up
  (100–150 sites of cookies, YouTube, Drive, third-party logins) before first spend; first billing
  ≈ $15/account vs $40+ for a bought aged account. None of it touches Merchant Center.

## Feature map: SaaS feature → this skill

| Feature (Meta-world expectation) | Google reality | Ours |
|---|---|---|
| Import accounts by cookies/token | not possible — API needs developer token + OAuth/SA on an MCC | operator hands MCC + token + customer ids (`00` §1) |
| Template → N accounts | — | `googleops bulk-plan/bulk-apply` (`10`), `{tag}` stamping |
| Creative uniquification | RSA text combos; image assets per account | spec per account; `uniquify.py` (meta) not ported — text ads need copy variants, not pixel noise |
| Dry run | — | `plan` = `validate_only` (Meta has no true equivalent) |
| Scheduled start | — | `activate --refresh-start YYYY-MM-DD` (date granularity; Google has no start hour) |
| Autorules | Google Ads Scripts / rules UI | not exposed; `monitor` verdicts + your scheduler |
| Spend/ban dashboard | — | `monitor --jsonl` (SUSPENDED/REJECTS/SPENDING/IDLE) |
| Card binding, top-up | UI-only on both platforms | `02` — the highest-risk moment on Google |
| Appeal | UI-only on both | `04` track classification first |
| Account creation | `CustomerService.CreateCustomerClient` exists under an MCC (API) but new accounts inherit the MCC's compliance history; MC sub-accounts via `accounts.createAndConfigure` (`12`) | not wrapped — cascade scope (`04`) makes mass-creation under one MCC the wrong default |

## Aged / ready account market (vendor claims, no independent audit)

| Vendor | Price | Claims |
|---|---|---|
| buydigitalaccount | fresh GMC $250 · fresh GMC+Ads $450 · reactivated $350 · aged 6–12 mo $600 · 1 yr+ $750 · GMC+Ads+MCC $900 | antidetect profile + proxy + SMS 2FA included |
| gmcshop.us | $399 (list $999) | GMC + Ads, "$6k–20k historical spend", delivered logged-in in GoLogin, residential proxy, billing pre-added |
| invcc | $249–700; suspension fix $249 | "2+ years old, clean history" |
| okayfy | $349–599 | "instant ad-ready" |

Delivery-in-antidetect-browser is the tell: these are farmed with the tooling above, not aged
organically. Reviews are mixed, including scam accusations. Buying one inherits an unknown
MCC/payment history — `04` cascade applies from day one.

## Where autolaunch value actually is on Google

The lift isn't launch speed (a Search campaign is a dozen operations) — it's **not dying at the
payment event and the destination review**. Spend engineering on `doctor` gates, tracking before
spend, review-layer discipline (`05`), per-account kill rules — not a UI bot.

## Google Ads Editor (desktop) — not an automation surface

Checked 2026-09-03 (Editor 2.13). Free Windows/macOS app: download account → bulk edit offline →
review change list → Post. Edits Search/PMax/Shopping/Demand Gen/Video/App; CSV and `.aes` import
across MCC children. **No API, CLI, plugin, or AI hooks** — GUI plus file import only; Playwright
cannot drive it, OS-level GUI automation is fragile and login-session-bound (persona hygiene, `01`).
No `validate_only`/PAUSED contract: Post applies live. Use only when an account has UI login but no
developer-token access, or for a human offline diff before a large manual edit; an agent may
generate the CSV, a human imports and posts. Never as the `googleops` path.

