# 05 — Automation channels (which pipe, when)

Agent-first ranking. The agent's write path is ALWAYS the API; every other channel exists for the
human layer or as a fallback. Composing rule: `validate_only` → PAUSED → human enable, regardless
of channel. Both platforms implement it: Meta via `execution_options: ["validate_only"]`
(meta-ads/13 §10.0 — per-endpoint support matrix there); Google specifics →
`references/06-google-lane.md`. Meta adapter: `meta-grey-ops/scripts/launch.py`.

| Channel | Agent use | Human use | Documented in |
|---|---|---|---|
| **Meta Marketing API** | Primary write path. System User token, validate_only dry run, PAUSED-first launch, resume-safe id log, `bulk.py` for N accounts, currency-offset guard | Reviews IDs before enable; owns token/asset assignment | meta-ads/13, meta-grey-ops/04 + `scripts/` |
| **Meta Ads MCP** (`mcp.facebook.com/ads`) | Reads, diagnostics and bounded edits. Live-verified 2026-09-02: 106 tools, write tools accept `attribution_spec`/`degrees_of_freedom_spec`/DSA but **not** `contextual_multi_ads` (creatives inherit multi-advertiser ON); no validate_only, one account per call; needs token scope `ads_mcp_management` and a per-account rollout flag. Writes land PAUSED | Sets ads MCP rules (Business Settings → Integrations → Ads MCP Server) | meta-grey-ops/02 §0, §5 |
| **Automated rules (Meta API)** | Arm the kill/alert ladder (count-form rungs, cents units, dry-run via adrules_history) | Sets confidence levels and verdicts | senior-buyer-ops/04 |
| **CSV / bulk files** | Fallback only — human-mediated, no atomicity, no validate_only. Meta: Ads Manager import lands as paused drafts, **blocked on fresh accounts** (error 3738001 → build via API/UI) | The right tool when a human must review thousands of rows first | meta-ads/02 §10, meta-ads/14 |
| **n8n / Zapier / Make** | Orchestration glue (lead → conversion upload, alerts). No no-code connector matches direct API for atomic multi-entity creation; n8n self-hosted = no per-execution ceiling | Alert routing to chat | `references/06-google-lane.md` for the Google leg |

Google-only channels and the Google-specific detail stripped from the CSV and n8n/Zapier/Make rows
above → `references/06-google-lane.md`.

Decision rules:

1. **Agent writes → API, full stop.** MCP only where its governance matches the task (read-heavy
   analysis, bounded writes); never route a launch through CSV/UI import — no validate_only there,
   Meta blocks fresh accounts.
2. **One spec format, two adapters:** campaign spec as validated JSON → deterministic code emits
   platform-specific API objects. The LLM never emits API calls directly. Meta adapter:
   `meta-grey-ops/scripts/launch.py`; Google adapter → `references/06-google-lane.md`. An LLM
   hand-assembling a Graph payload from prose is a regression, not a shortcut.
3. **Human layer sees**: draft IDs before enable, the daily spend→cost sync sheet (tracker-ops/03),
   and the rule history — nothing else needs a human channel.
4. **Reads are cheap everywhere**: the Insights edge (Meta) feeds the daily routine; the Google
   read path is in `references/06-google-lane.md`. Exports → `meta-ads/scripts/analyze_ads_export.py`
   (meta-ads/12) only when a human asks for a file.
