# Meta Business Portfolio (formerly Business Manager) — Setup & Navigation

Reviewed **2026-07-24**. UI varies by rollout; "Business Manager" in older sources = same surface.

---

## 1. Portfolio vs profile vs Suite vs Ads Manager

- Personal profile creation limit: **2 portfolios/profile** [practitioner; Meta Support confirmed tested-profile: **lifetime quota**, not reset by leaving/deleting, membership in others' portfolios doesn't count]. No public limit table.
- Every profile auto-gets a **personal ad account** (on first boosted post) — running business ads from it instead of a portfolio account strands assets on the individual.
- **Assets belong to the Portfolio, not a person's profile** — survives staff/agency turnover. Renamed 2024 (old `business.facebook.com` links redirect).
- 2025 rollout: **managed Meta accounts** — company-managed, email-based, not tied to a personal profile [uncertain: rollout/region vary].
- Business Suite = daily workspace (publishing, inbox, insights, simple ad creation, has mobile app). Portfolio = ownership/access container, no mobile app. Switch via Suite Help → "Go to Business Manager"; Portfolio hamburger → "Meta Business Suite."
- Ad account can exist without a Portfolio; once claimed, access/billing/partner perms move to Portfolio level.
- Portfolio required for: Suite; business-owned ad accounts; Shops; domain verification; monthly invoicing; social-issues/elections/politics ads; agencies/partners; multiple Pages/ad accounts.

## 2. Creating a Portfolio

`business.facebook.com/overview` → Create an account → business name, your name, business email → Submit → verify email (check spam; unverified blocks later steps).

- Consistent, real naming across Portfolio/Page/IG — mismatches complicate verification/linking.
- ≥2 trusted, separately-secured full-control owners (single-owner = continuity risk; more full-control users = more takeover surface).
- Fill Business Portfolio info (legal details, primary Page) immediately — incomplete info is a common verification/restriction trigger.

**Creation-limit recovery** [W: access ≠ quota]:
- `Leave` removes access only, doesn't free quota; removing a Page/IG asset doesn't either.
- Tested-profile Meta Support reply: leaving **or deleting** does not restore the lifetime quota; not increasable; no 24/48h reset — **conflicts** with the live creation-error UI, which suggested deleting an existing portfolio. Preserve both, don't generalize, escalate manually.
- Deletion can be blocked by System Users, Pixels/datasets, or a problem ad account.
- If limit persists: preserve Page/IG, ask support to delete the inaccessible portfolio or review the profile restriction; else have an authorized colleague create the company portfolio (confirm they can accept access before migrating assets). Never use bought/shared/fabricated profiles as a workaround.

## 3. Business Verification

Not mandatory for basic advertising; required/recommended for WhatsApp Business API, certain API/app features, stronger ownership evidence in review, some advanced/partner/politics features.

- Gotcha: **"Start verification" is often greyed out** until a verification-requiring feature is attempted (e.g. adding an app/WhatsApp number) [uncertain: exact trigger list].
- Path: Business Settings → Security Center → Business Verification → Start verification → country of HQ → legal details → Meta matches public records → upload docs if unmatched → confirm phone/email.
- Docs must show legal name + address/phone, match portfolio info **exactly**, supported language, utility-bill-type docs **≤~1 year old** [uncertain source]. Accepted: incorporation certs, business licenses, tax registration, business bank statements, utility bills, business credit reports, country-specific registrations (Udyam, PAN). **Rejected**: invoices, POs, self-filed tax returns, personal bank statements, website printouts, self-made letterheads/flyers.
- Timeline: **~48h** (Superchat, 2026) to **30 days** (Klaviyo, 2026), queue/quality-dependent. Status in Security Center. Common rejections: name/address mismatch, expired/self-made docs, unsupported language, blurry scans.

## 4. Ad accounts: adding, creating, limits

- **Currency and time zone are permanent** — mistake means a new ad account.
- Ad account belongs to **one** Portfolio only; "Add" fails if another portfolio owns it → use "Request access" instead.
- Voluntarily closed accounts normally reactivate via Ads Manager once billing resolved — check state before creating a replacement (distinct from policy-disabled).
- New portfolios start at **1 ad account**; grows with spend history, on-time payments, compliance [practitioner]. Check: Business Settings → Business portfolio info → Ad account creation limit [uncertain: label placement]. No fixed tier table published.

## 5. Pages and Instagram professional accounts

- IG must be a **professional account** (Business or Creator — commerce/partner/messaging features vary by type/region); prefer Business for companies. IG should be linked to the FB Page (Page → Settings → Linked accounts, or Accounts Center) for cross-posting/inbox/IG ad identity.
- Adding a Page requires **full control / ownership-level** Page access; if claimed by another Portfolio, "Add" fails → request access or transfer.
- Page access splits: **Facebook access** (full control or partial: content/messages/ads/insights) vs **task access** (granular) — task-access-only people may not be able to move a Page into a portfolio.
- Adding IG: must not already be connected to a *different* Portfolio (disconnect there first). **Assign people to the IG asset after adding — adding someone to the portfolio does NOT auto-grant asset access** (most common setup mistake).
- Verify FB↔IG link in Accounts Center → Sharing & logging in; if Page isn't listed, IG won't appear as an identity option in Ads Manager.
- Troubleshoot order: professional-account status → Business vs Creator eligibility → Page/portfolio ownership → operator permissions → existing connections → stale login sessions. Creator status alone is rarely the actual blocker.

## 6. People, roles, partners, system users

- Invite by the email tied to their FB profile; shows "Pending" until accepted.
- Roles (2024+): **Full control** (was admin) — settings/people/tools/all assets, can delete portfolio, cap at 2–3 trusted owners. **Partial access** (was employee) — assigned assets/tools only. **Finance** perms (billing without full control); **temporary access** (time-limited, auto-revoked).
- Two-layered access: portfolio-level (settings/people) + asset-level (per Page/ad account/dataset, task toggles) — adding a person ≠ assigning assets.
- **Partners** (correct agency model — client keeps ownership): Users → Partners → Add → paste agency's Business ID → select assets/perms. Reverse: "Ask a partner to share their assets." Remove is instant, no data loss, assets stay with owner.
- **System users**: server-to-server identities for API/tokens. Assign the app + each required ad account/Page/IG/dataset/catalog to the System User before generating its token — token scopes and business-asset tasks are separate layers. A successful asset-list `GET` does not prove campaign-write access; run a zero-spend `PAUSED` write + Page/IG creative probe before full build (`13-api-access-billing-launch-operations.md`).

## 7. Payments and spending limits

- Payment method varies by country: cards most common; PayPal/direct debit some markets; manual prepay some countries; monthly invoicing/credit lines only via application.
- No universal rule flags every prepaid/virtual card as high-risk; diagnose failed transaction, amount due, verified/default card, method eligibility, and account restriction **separately** — zero balance + verified card alone doesn't restore an account.
- Never transmit card data/verification codes via chat or API tooling — only Meta's trusted UI.
- **Account spending limit**: hard lifetime cap on total ad-account spend — not monthly, not per campaign [practitioner: Jon Loomer; Meta Help Center via Agrowth 2026-01]. At cap, **all campaigns stop delivering but still show "active"** (editable/resumable) — classic false-restriction symptom; check here before assuming restriction. Not available for manual-payment (prepaid) accounts. Distinct from campaign/ad-set budgets, billing thresholds (auto-charge points), and Meta's risk-based new-account caps (lift with billing history, typically months). Gotcha: exhausted $0-limit accounts look "banned". Reset continues spend under same cap.
- **Daily spending limit**: Meta-imposed, dynamic, grows with history — not manually settable.
- **Campaign spending limit**: optional per-campaign cap.
- IG "ad spending limit" in the promotion flow = same account spending limit.

## 8. 2FA and security

- Portfolio-wide requirement: Business portfolio info → Business options → Two-factor authentication → Admins only / Everyone / No one. Only full control can change it.
- Meta requires 2FA for **certain** portfolios older than **90 days** [not documented as universal] — require it for everyone with asset access regardless.
- Side effects: people without personal 2FA lose access until enabled; cookie-clearing browsers demand a code every login; third-party tools require a login code next sign-in.
- Account quality surface shows restriction status for portfolio/ad accounts/linked profiles + appeal entry.
- Hygiene: remove ex-employees/agencies immediately; audit People/Partners quarterly; watch for phishing impersonating "Meta Business Support" (leading cause of portfolio takeover → ad bans).

## 9. Settings panel map

`business.facebook.com/settings` (Suite settings gear redirects here — no separate "Suite settings").

| Section | Contains |
|---|---|
| Users | People · Partners · System users |
| Accounts | Pages · Ad accounts · Business asset groups · Apps · Instagram · WhatsApp · Commerce |
| Data sources | Catalogs · Datasets · Pixels · Custom conversions · Audiences — dataset groups events across sources; Pixel is the web source, may share its ID with the dataset |
| Brand safety | Domains (verification) · Block lists |
| Security center | Verification, 2FA requirement, alerts |
| Business portfolio info | Legal details, primary Page, ad account creation limit, 2FA option, permanently delete business |
| Billing & payments | Balances, methods, invoices, credit lines |
| Account quality / Business Support Home | Restrictions/appeals |

Legacy mapping: Business Manager=Portfolio; Admin access=Full control; Employee access=Partial access; Business Info=Business portfolio info. Do NOT map Pixels directly to Datasets — Pixel is the web source, datasets can group its events.

## 10. Restriction diagnosis and structural practices

- Restrictions can hit a person, Page, ad account, portfolio, payment method, or single ad — check the exact affected asset/reason, don't assume portfolio-wide. First stop: Account quality/Business Support Home + Delivery status in Ads Manager.
- Common failure → cause map: inauthentic/shared profiles (identity-rule violation); missing requested verification/2FA (blocks only the workflow requiring it, not a blanket restriction); payment declines/unsupported methods (resolve exact message, don't blanket-reject prepaid/virtual); compromised credentials (respond to actual checkpoint, no generic "warm-up"); asset ownership disputes (verify recovery window before deleting anything); shared logins/broad full control (one compromised admin takes down the whole portfolio — use partner/partial access); wrong IG linkage; incomplete contact details (blocks verification/recovery comms, no evidence of a hidden trust-score penalty); unmanaged spending limit (mimics restriction — ads stop, show "active"); running ads before foundation is clean (unclaimed Page/personal ad account/no Pixel ownership complicates migration, can strand data with the asset owner).
- Structural practice: one portfolio per legal entity; agencies get partner access only; 2+ full-control admins, rest partial/temporary; quarterly access audits; verification+2FA day one; healthy + backup payment methods; budgets from economics/risk, not account-aging ritual.

---

## Sources

1. leadsie.com/blog/meta-business-manager-vs-meta-business-suite-differences — Suite vs Portfolio roles, rename, managed accounts (practitioner, 2026-07-22).
2. badrhinoinc.com/blog/meta-business-suite-vs-business-portfolio — ownership mistakes (practitioner, 2026-07-22).
3. graphed.com/blog/how-many-meta-business-accounts-can-i-have — 2-portfolio limit, ad account limit growth path (practitioner, 2025-12).
4. jonloomer.com/glossary/ad-account-creation-limit — limit starts at 1, grows with history (practitioner, 2023).
5. jonloomer.com/campaign-spending-limits-account-spending-limits-daily-spending-limits — spending-limit types, "stopped but active" (practitioner, 2023).
6. help.klaviyo.com/hc/en-us/articles/40116148219163 — verification click-path, docs, up to 30 days (partner doc, 2026-03).
7. help.superchat.com/en/articles/14982 — verification docs, ~48h review (partner doc, 2026-07).
8. support.chatarchitect.com (2FA setup mirror) — 90-day 2FA requirement language (accessed 2026-07-22).
9. support.properti.ai (Page/IG setup) — click-paths, cites official Meta help URLs (accessed 2026-07-22).
10. tj21.com — partner access via Business ID (practitioner, 2025-12).
11. socialschool4edu.com — two-admin rule, Meta support recovery process (practitioner, 2025-01).
12. superads.ai/blog/fix-facebook-ads-account-restricted — restriction levels/causes (practitioner, 2025-09).
13. favfly.com/post/meta-ads-account-disabled — appeal evidence, prevention (practitioner, 2025-04).
16. graphed.com/blog/how-to-change-facebook-ad-billing-threshold (practitioner, 2025-12).
17. leadsie.com/blog/request-access-to-facebook-page (practitioner, 2026-06).
18. facebookblueprint.com — official portfolio-setup course terminology (accessed 2026-07-22).
19. Live product observation — deletion blocked by System Users/Pixel/dataset/ad account issues; leave+creation-error conflict (account-specific, 2026-07-24).
20. facebook.com/help/messenger-app/195296697183682 — warns against shared/inauthentic profiles (official).
21. Meta Support response, tested profile — lifetime 2-portfolio quota, no reset, recommended colleague-created portfolio (official, account-specific, 2026-07-24).
22. facebook.com/help/1392616391875085 — Account Status shows profile/Page restrictions (official).
23. facebook.com/business/ads/review-policy-guidelines — restriction scope, Business Support Home (official).

## Gaps

- Official Help Center pages not directly fetchable; click-paths corroborated only via partner-doc mirrors — re-verify labels live.
- Ad account creation limit: no fixed tier table; increments unverified.
- Billing threshold starting amounts/increments by country: unverified [uncertain].
- Portfolio creation limit reset timing: account-specific Support reply conflicts with live UI text; not a confirmed universal policy.
- Managed Meta accounts rollout: eligibility/flow for 2026 unverified.
- "Start verification" greyed-out trigger list: unverified.
- Settings left-panel ordering: A/B-tested, varies.
- Document recency (~1 year): from partner docs only, not directly verified.
