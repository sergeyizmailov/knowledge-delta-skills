# 12 — Merchant Center in the grey lane

Reviewed 2026-09-02. Practitioner sources: Shopify Community (2023–2026 threads), StubGroup,
Store Growers, FeedShield, Search Engine Land (Horn, 2026-04), DataFeedWatch, Octo Browser blog,
RU arbitrage blogs; official policy where named. Clean mechanics → `google-feed-ops/04`.

## Cascade: the one fact that changes the plan

- **A suspended Ads account linked to a Merchant Center account suspends the MC account, and
  unlinking afterwards does not clear it** (official, answer/13030286 and 15263425: fix the Ads
  suspension first, then request MC review). Practitioners report the other direction too — MC
  Misrepresentation → linked Ads shows a "Terms & Conditions"/Circumventing-systems suspension —
  both supports point at each other ("fix the other side first"). Treat MC ↔ Ads as **one blast
  radius**; the link is the fuse.
- Shared payment profile/card/address across MC, Ads, payments: named triggers for "suspicious
  account activity" (DataFeedWatch, Octo). Octo's claim that a shared payment profile blocks
  Ads+MC+AdSense together is vendor-reported, unverified.
- A **second MC account** after suspension, same domain/business/Shopify store: reported
  suspended again and reframed as Circumventing systems (multiple independent threads, 2023–2025).
  One Shopify store may link to one MC; one Search Console property associates with one MC
  (official).
- Domain **history**, not domain age, is the risk: expired domains with a prior different
  business or a prior suspended MC carry the flag. No practitioner evidence a freshly registered
  domain is penalized for being new.

## Grey-specific answers

| Question | Answer (2026-09-02) |
|---|---|
| Does anyone cloak Shopping landing pages? | **Not found in any practitioner source**, EN or RU. Cloaking guides cover Search only. Google runs a separate **StoreBot** crawler for product pages (official); feed price/availability crawl is continuous, so a filtered lander desyncs the feed → preemptive item disapproval, then account review. Default: don't run Shopping through a review layer at all (`05`). |
| Affiliate store redirecting to a partner checkout | Official policy: Shopping ads may not promote affiliate/PPC links to a third party's products (except via a CSS); enforcement "upon detection, without warning". No path. |
| Dropshipping | Permitted (practitioners date the change ~2023); suspension segment is thin, templated, AliExpress-image stores. Named automated triggers (vendor, gmcsuspension 2026): image fingerprint match against AliExpress/Temu/CJ, identity mismatch across WHOIS/footer/payments (down to "Co" vs "Company"), promised shipping time vs actual, vague returns, feed price drifting from supplier price. FeedArmy's rep: legit physical stores approve "pretty much instantly", dropship needs "half a year or more" of reputation — disputed by others. |
| Aged/rented GMC accounts | $250–900 market (`11`); delivered inside an antidetect profile with proxy and SMS number, i.e. farmed. Unknown MCC/payment history; cascade rule above applies day one. |
| Multi-store operator structure | Advanced account (ex-MCA) + sub-accounts; parent claims the top domain, sub-accounts inherit. Default 50 sub-accounts (request more). Whether one sub-account's suspension propagates to siblings: **not found either way** — assume shared identity signals (payments, address, GTM) propagate, structure alone doesn't isolate. |
| Appeals | 1–3 attempts before the review button locks; each denied review adds a cool-down (first ≈7 days, growing). Appealing before the site is fixed burns an attempt. No programmatic appeal (`google-feed-ops/05`). Support is scripted, may not state the cause; a Product Expert (Flossie/FeedArmy) cited as more useful than chat. |
| Identity verification | Government ID/business registration demanded when Google can't confirm the business; "maximum verification attempts reached" is a terminal-looking state. Same rule as Ads (`06`): never submit false documents. |

## Operating rules for a grey team running Shopping

1. Decide per project whether Shopping is worth linking at all: the MC link turns an Ads burn into
   an MC burn and vice versa. Keep Search-only accounts unlinked.
2. One MC per business identity per domain; never a second MC to escape a suspension.
3. Payment profile, business address, phone, GTM/GA/Search Console: unique per MC↔Ads pair, same
   discipline as `01` §linking signals.
4. Feed-only PMax or Standard Shopping — no cloak, no redirect chains, `link` = the page the crawler
   will price-check, checkout total incl. tax/shipping = feed.
5. Fix before appeal; count attempts; log what changed between attempts (`04` one-variable rule).
6. Store trust signals are the actual review: About, contact phone + address matching MC business
   info, specific returns window, payment logos only for methods that work at checkout (a
   documented single-case fix, dev.to 2025-03), no placeholder text, SSL.
