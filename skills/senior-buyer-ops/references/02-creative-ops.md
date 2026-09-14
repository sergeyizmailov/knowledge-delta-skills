# 02 — Creative ops (production, not diagnosis)

meta-ads/12 diagnoses a finished ad. This is the pipeline that keeps winners coming: in
broad/Advantage+ delivery the creative is the main lever, so creative THROUGHPUT — not targeting —
is usually the real bottleneck.

## Concept model (keep flat)

Concept = angle (claim/emotion, e.g. "news exposé", "quiz", "big win") × hook (first 1-2s/first
line) × format (static, UGC video, screen-record). Test at the ANGLE level first; hooks/formats
are variations under a winning angle. A new angle is a new bet, a new hook is an iteration.

## Explore vs exploit (run both, don't collapse into one)

Two modes, different rules — winner-lineage alone converges to a local maximum, so reserve a
fixed EXPLORE quota (~20-30% of test budget, a lever):
- EXPLOIT (iterate winners): CONTROL (current best) vs CHALLENGERS descended from proven winners —
  same angle, new hook/format. Change ONE variable per variant (hook OR first frame OR CTA OR
  proof) so a win is attributable and iterable. Promote only on the payout metric, not CTR
  (small-sample promote rule: measurement-experimentation-ops/01 § "Comparing two assets on small
  counts").
- EXPLORE (new concepts): a genuinely new angle changes hook + visual + narrative + proof at once
  — expected, don't force one-variable here. Testing the ANGLE bet, not isolating a cause; isolate
  later if it wins.
- Record winner lineage (which angle-family prints) AND explore results, so scaling pulls from
  exploit while explore keeps refilling the top of the funnel.

## Creative intelligence (tag at the attribute level, not the ad level)

A winner is a BUNDLE of attributes; logging "ad X won" throws away why, and the ad dies while its
winning proof-type or mechanism could live on. Tag every tested creative on: persona /
market-awareness stage / dominant desire · mechanism ("how it works" claim) · proof type (UGC,
screenshot, authority, before/after-proxy, data) · objection handled · core emotion · angle · hook
· format · funnel version (which prelander/offer it ran to).

- Score COMBINATIONS, not isolated winners: an angle×proof×emotion (and hook family) printing
  across multiple unrelated accounts/GEOs is strong signal; a single-account winner is
  weak/unconfirmed until replicated. Briefs (below) specify the bundle to reproduce, so production
  compounds on known-transferable parts.
- Decay is per-attribute on different clocks: a HOOK usually fatigues per audience (rotate fast),
  while an ANGLE/MECHANISM/EMOTION can fatigue market-wide as the scene copies it and CTR decays
  broadly. Cue (corroborate, don't act blind): the same angle suddenly flooding spy tools (below)
  often signals market saturation — cross-check your own CTR trend before jumping to a new
  mechanism rather than just a new hook. Track each axis as its own time series, not one blended
  fatigue number.

## Multi-stage graduation

Don't jump a new creative straight to a scaling account. Graduate: cheap explore test → if it
clears the payout bar, promote to challenger vs control → if it beats control, migrate to a
scaling account. Each stage has a bigger budget and a higher bar; kill early stages fast, protect
late-stage winners.

## Fatigue

Leading signals, per ad on the same audience: rising frequency with CTR/CVR decaying and CPA
climbing = fatigue, not auction noise. Rotate to the next challenger from the backlog BEFORE the
winner craters; don't edit the winning ad (a significant edit can re-enter learning,
meta-grey-ops/04) — launch the successor.

## Backlog & briefs (throughput is the bottleneck)

- Keep a creative backlog sized to test cadence — if you can test N/day, you need ≥N new
  concepts/iterations queued or scaling stalls waiting on creative.
- Brief to designer/editor = angle + hook + reference (spy link) + must-have proof/compliance
  notes + aspect ratios (4:5, 9:16) + what NOT to show (policy: before/after, personal-attribute
  copy, prohibited claims per vertical playbook). A precise brief is the difference between one
  usable cut and ten rejects.

## Comment ops (the comment thread is creative)

On Meta, comments are a conversion surface, not a cleanup chore (practitioner practice,
Comdrop-class tools): seed threads that EXTEND the creative — mini-stories, Q&A objection
handling, controlled debate — pin the answer the ad didn't give. A sterile thread (all negatives
deleted) reads fake and wastes the surface. Native-post variant: run without the CTA button, link
in first pinned comment (sweeps technique; ~10× organic/viral reach claimed on product content
[single source]). Budget comment ops as a production line item, same as cutting variants.

## Spy / creative intel (current 2026)

- AdSpy — deepest FB/IG DB (comment + affiliate-network filters); best for grey.
- AdHeart — FB/IG, strong in CIS grey scene.
- SpyTrend — Meta+TikTok. The differentiator is **advertiser/webmaster clustering**: ads
  grouped into one team by pixel + landing domain + Page ID, so you pull a competitor's whole
  operation (active-ad count over time, which domains and Pages are live now) instead of
  single creatives. Also filters on **likes** (a proxy for real volume — and for teams who
  self-like and script comments to warm an ad, `02` comment ops). Per-ad transcript/translate
  helps adapt a foreign creative. **Official MCP server** (`mcp.spytrend.com/mcp`, OAuth 2.1,
  ~20 tools) — the one spy in this list an agent can query directly; Pro $79/mo, free tier
  [vendor site, verified 2026-09-09]. Corpus size and coverage claims are the vendor's own.
- Anstrex — native + push, rips landing/pre-lander pages (nutra pre-landers).
- Meta Ad Library — official, no spend/performance, no cloaked/rejected ads → baseline recon only.
- GEO-local spy farm [MagicClick 2026]: seed a GEO-reg acc → search/join/like casino Pages → click
  5–10 ads, ~30s on LP → ~50% casino in feed. Mobile session (many affiliates mobile-only). Then
  Library-by-Page for the full set. Spy tools miss cloaked/rejected; this sees live delivery.
