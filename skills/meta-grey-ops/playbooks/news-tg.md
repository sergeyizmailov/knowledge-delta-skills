# Playbook — News funnels: FB ads → news pre-lander → Telegram subscription

Reviewed 2026-08-28. Filled from live work (Aug 2026); benchmarks are one team's — re-verify per team. Vertical: "news-style" crypto/finance persona funnels to a TG channel.

**Funnel:** FB/IG ad (news-style image, no ad-level texts) → Keitaro campaign URL (cloaca: bots/reviewers → white page, real users → black news pre-lander) → pre-lander (fake news article/persona story) → CTA to Telegram channel. Lead = TG subscription via postback. Deeper funnel (regs, deposits, revenue) happens behind the channel, judged by TL — cheap low-quality subs are a trap.

**Objective/event:** Leads (NOT Sales — Sales blocks Lead/Submit Application events). Conversion event: Submit Application on shared team pixel.

**Geo/targeting:** USA 20+, Advantage+ broad, auto placements; kill placements with suspiciously cheap CPM and zero leads.

**Creative constraints:** news-photo style with baked-in headline text; no ad-level primary text/headline (moderation rule); display link = big news domain (real destination stays the tracker link); CTA Learn more; all enhancements off except Hide price; multi-advertiser off. Uniquify per account before upload (byte-level only, below Meta's near-duplicate threshold — not real variance, `13`). Leads/Submit Application starts at 06:00–08:00 account geo-time, never 00:00.

**Review traps / what kills the account:**
- A "news-style" persona alone does NOT trigger Special Ad Category — trigger is CONTENT: advocating/debating a topic of public importance (economy, health, crypto regulation) can fall under Social Issues/Elections/Politics. Keep creative on the product/offer, not the debated issue.
- Financial/crypto angle can pull the ad into FINANCIAL_PRODUCTS_SERVICES or the crypto/financial authorization gate — see `crypto-trading.md` + `10` before running a finance-flavored funnel.
- Accounts die in batches early (fresh stock, first spend) — expected, replace, no appeal. No creative-level reject flags even when accounts die — account quality is usually the trigger, not creative content.
- FB profile restrictions come from IP/device inconsistency (multiple sessions), not from ads — see `01`.

**Kill/verdict rules (agreed pattern):**
- Creative: no lead after ~$20 (1.5–2x target CPL) or CTR <2% → off.
- Adset: CPL stable above $12–15 after 2–3 leads → off.
- Account: verdict after ~$50 or 3 days — CPL persistently >$15–25 → replace.
- Zero impressions in 2–3 days with live campaign → replace (normal for agency stock, don't fix).
- Automated rule: Spend >$20 lifetime AND Results <1 → turn off ad sets, run continuously.

**Economics (one team, US GEO, 2026-08):**
| Metric | Value |
|---|---|
| Target CPL (subscriber) | $10; working range $9–11 on seasoned accounts |
| Healthy account | CTR 5–7%, CPM $16–32, CPC $0.28–0.50 |
| Fresh agency accounts | CPM $44–68 (2x premium), normalizes over days |
| Per-account variance, same funnel | $5–25 CPL — account quality is the decisive variable |
| Click→sub conversion | ~5–6% of Meta link clicks |
| Payout | % of spend on CPL sliding scale (e.g. $8→12%, $10→10%, $12→8%) |

**Metrics discipline:** TG subscription = tracker "leads" (Keitaro). If a deeper postback flips the same click lead→sale, subs = leads + sales (`tracker-ops/01`). Tracker "conversions" counts the whole funnel's postbacks — this team observed ~3.5–4x lead count, but ratio is setup-specific, never use as a CPL denominator. Cross-check: Meta pixel Lead ≈ tracker leads. Day = ad account timezone day for both spend and leads. Bot-share spikes in tracker = cloaca filtering hard — watch for domain/account ban after.
