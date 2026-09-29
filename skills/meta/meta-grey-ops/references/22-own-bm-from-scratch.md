# 22 — Own BM from scratch (system user, app, pixel + CAPI, Page/IG, billing)

Written 2026-09-29 from the "<BM name>" BM (<BM_ID>, not business-verified): tr-1
act_<ACCOUNT_ID> (USD, Europe/Istanbul) and CF1 act_<ACCOUNT_ID> (USD, America/Los_Angeles).
Facts live in `02` (access), `03` (BM/asset sharing), `18` (Page/PBIA); this file is the order.

1. **Portfolio.** Create it, verify the email, fill in the business info, ≥2 separately secured
   full-control owners, 2FA (`meta-ads/01` §2, §8). New BM = 1 ad account cap (`03`); a second account
   means a second BM plus partner share.
2. **App.** One Business-type app per BM, use cases from `02` §1, app **Live** (Privacy Policy URL 200).
   Tier is Limited on own assets: ≈300 calls/h per ad account (`02` §4).
3. **System user.** Admin role if the agent must create pixels/catalogs or assign assets, else Employee.
   Assign **Full control** per asset (ad accounts, Page, IG, pixel/dataset, app); portfolio membership
   assigns nothing. Token expiry Never, scopes `02` §3. On this BM: `agent_admin` (ADMIN), `api_bot`, plus a
   Conversions API system user. `doctor --scope provisioning` before any BM write.
4. **Workspace.** Separate project dir with its own `workspace.json` (profiles `tr1`, `cf1`, `token_kind`,
   `currency`, `timezone` = the ACCOUNT tz, `defaults.allow_no_proxy` if no proxy is intended, `16`).
   Order: `workspace validate` → `assets verify --scope core` → `doctor`.
5. **Pixel + CAPI.** Create the WEB pixel/dataset by hand in Business Settings → Data sources (the Pixel
   Terms of Service prompt, 1784018, cannot be accepted via API, `meta-ads/14`). A pixel shared to the BM
   is NOT on the accounts: attach it to every ad account (Datasets → Add assets, Full control) and
   check `GET /act_<id>/adspixels` (`04`, 1815045). `POST /{pixel}/shared_accounts` only works when one
   business has access to both (`03`). CAPI token = pixel-scoped or a system user with Full control on the
   dataset; prove it with `metaops business capi test --event Lead --test-code TEST…`; the PWA builder
   gets dataset id + token (`11`). Automatic Advanced Matching off on a money-page dataset (`07`).
6. **Page + Instagram.** Page fields are set once at create time and then frozen (`18`). The PBIA cannot be
   created by API (deprecated for all versions since 2025-04-21): Ads Manager → ad draft → Identity →
   **Use Facebook Page** → discard the draft. Until then `doctor` WARNs and `launch.py` aborts (it was the
   only doctor blocker on the own BM, 2026-09-29).
7. **Billing.** Card in the UI only, never in chat. The **billing threshold can be neither read nor set via
   API** (UI only); a change made by the operator was rolled back by Meta on 2026-09-29. Card
   rules (one card per few accounts, never a card from a disabled account): `03`.
8. **Token fallback.** A scraped EAAB (app "Power editor" 119211728144504) passed `metaops doctor` (14 ok,
   incl. `validate_only`) from a Mac without a proxy on 2026-09-29. `debug_token` on a first-party
   token returns #100. It dies with the login session; prefer the system-user token (`02` §5).
9. **Before the first campaign.** `metaops pace` clean, plan file (`19`), UI-first launch on a weak/new
   account (`24`), one create per account per 3 h.
