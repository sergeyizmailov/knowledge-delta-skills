# Sources by Domain

URLs verified 2026-09-08 (see SKILL.md for the single verification-date policy). Root domains where paths rot; renames/relocations flagged since these entities churn faster than this file will be edited.

## Cybersecurity

Techniques/tools: MITRE ATT&CK Navigator (https://mitre-attack.github.io/attack-navigator/) · PortSwigger Research (https://portswigger.net/research) · Project Zero — moved off the old blogspot.com address (https://projectzero.google/) · DEF CON media (https://media.defcon.org/).

CVEs/exploits: canonical CVE home is https://www.cve.org/ — cve.mitre.org now only redirects to an archived page · NVD (https://nvd.nist.gov/, API https://services.nvd.nist.gov/rest/json/cves/2.0) · GitHub Advisory DB (https://github.com/advisories) · OSV (https://osv.dev/) · ExploitDB (https://www.exploit-db.com/) · Packet Storm, relocated (https://packetstorm.news/ — old packetstormsecurity.com redirects here).

Malware/threat feeds — volatile, cross-check against a vendor blog or MITRE before treating as ground truth: ANY.RUN sandbox (https://any.run/) · VirusTotal (https://www.virustotal.com/) · MalwareBazaar (https://bazaar.abuse.ch/) · URLhaus (https://urlhaus.abuse.ch/).

Vendor research blogs (Tier 2; acquisitions/rebrands move these — verify before citing): Unit 42/Palo Alto (https://unit42.paloaltonetworks.com/) · Mandiant, now under Google Cloud (https://cloud.google.com/security/mandiant) · Talos/Cisco (https://talosintelligence.com/) · CrowdStrike (https://www.crowdstrike.com/en-us/blog/) · Securelist/Kaspersky (https://securelist.com/) · Sekoia, .io → .com (https://www.sekoia.com/) · The DFIR Report — real-intrusion case studies (https://thedfirreport.com/) · Krebs on Security (https://krebsonsecurity.com/).

## Web Development

https://developer.mozilla.org/ (HTML/CSS/JS/Web APIs) · https://caniuse.com/ (support tables) · https://github.com/tc39/proposals (upcoming JS) · https://spec.whatwg.org/ (living standards) · https://web.dev/ (perf, PWAs, Core Web Vitals). Framework-specific docs (React, Next.js, etc.): use a docs-index tool first — `sources-and-apis.md`.

## Cloud / DevOps

Vendor docs: https://docs.aws.amazon.com/ · https://cloud.google.com/docs · https://learn.microsoft.com/en-us/azure/.
Ecosystem: CNCF Landscape (https://landscape.cncf.io/) · Artifact Hub — Helm/OPA/Falco (https://artifacthub.io/) · Terraform Registry (https://registry.terraform.io/) · Kubernetes docs (https://kubernetes.io/docs/) · KEPs (https://github.com/kubernetes/enhancements).

## AI / ML

Models/datasets: https://huggingface.co/ · trending papers: https://huggingface.co/papers/trending.
Research leads: arXiv cs.AI/cs.CL/cs.CV/cs.LG · Connected Papers (citation graph, `sources-and-apis.md`) · Lilian Weng's blog (https://lilianweng.github.io/, ML summaries).

**Benchmarks — volatile, names/owners/domains churn**: Chatbot Arena → LMSYS → LMArena → arena.ai (as of 2026) — re-resolve the current canonical home before citing any leaderboard, don't trust the last URL cited anywhere including here. Open LLM Leaderboard v2 (https://huggingface.co/spaces/open-llm-leaderboard/open_llm_leaderboard; v1 retired 2024, scores not comparable across versions) · MTEB (https://huggingface.co/spaces/mteb/leaderboard) · HELM/Stanford (https://crfm.stanford.edu/helm/) · LiveBench, contamination-resistant (https://livebench.ai/) · Artificial Analysis, vendor benchmarks + pricing (https://www.artificialanalysis.ai/). Prefer a paper's own reported numbers over a leaderboard aggregate — prompts, decoding settings and quantization differ.

## Crypto / Blockchain

Standards: https://eips.ethereum.org/ · https://docs.soliditylang.org/ · https://ethereum.org/developers/docs/.
Audits/security: OpenZeppelin (https://www.openzeppelin.com/security-audits) · Trail of Bits (https://blog.trailofbits.com/) · SWC Registry (https://swcregistry.io/) · Rekt News, hack postmortems (https://rekt.news/) · Code4rena (https://code4rena.com/) · Sherlock (https://www.sherlock.xyz/) · Immunefi, bug bounties (https://immunefi.com/).
Tools: Slither (https://github.com/crytic/slither) · Mythril — org renamed, now ConsenSysDiligence not Consensys (https://github.com/ConsenSysDiligence/mythril) · Echidna (https://github.com/crytic/echidna) · Foundry (https://github.com/foundry-rs/foundry).

## Infrastructure/asset search

Shodan (https://www.shodan.io/) · Censys (https://search.censys.io/) · FOFA, China-focused (https://en.fofa.info/). ZoomEye returns a bot-block to a plain HTTP client even though the site is live — confirm reachability with a browser-capable fetch before ruling it out. Run two or more of these together for coverage; none is complete alone.
