# Write-up: AI Proposal Triage Design (MATACS-TH-2026-02)

## 1. AI vs. rules

**AI does three things.** (1) Extraction: it reads each proposal's text and returns structured facts (licence held, WSIB, insurance, installs, price, weeks, warranties, team items), each with a verbatim quote. (2) A second check that asks only "does this text address a reviewer or a system?". (3) Drafting the one-line reason from scores already computed.

**Code does everything else:** file and text checks, quote verification, mandatory gates, hard limits, all scoring arithmetic, ranking, status and logging.

**Why there.** Proposals are free text, so reading them needs language understanding. Deciding who passes and how many points a fact earns is a fixed admin rule, and code is exact, repeatable, free and cannot be talked into another answer. The line: AI may describe what a document says; it never decides what that is worth.

## 2. Consistency and explainability

Scores come from code applied to stored facts, so the same facts under the same criteria version always give the same ranking. The only variable part is extraction, so I pin the model and prompt version, use temperature 0 and a fixed output schema, and cache results against the file hash. Ranking twice reuses the cache and gives an identical result. If a file is re-extracted, two runs are compared and any fact that differs goes to a human instead of being silently chosen.

For explainability, each proposal opens a breakdown: per criterion, the fact, its quote from the document, the rule applied, the score and the weighted points. The reason line is generated from those numbers and cannot cite anything outside them.

## 3. Human in the loop

- **Confirm facts.** The reviewer always sees the facts behind the mandatory gates, plus anything missing, low-confidence or whose quote failed verification, and can correct them.
- **Resolve flags.** Flagged proposals (here C and D) get no rank until a person disqualifies, asks the bidder to clarify, or releases them.
- **Override.** A reviewer can change a fact or a position, but must give a written reason; the system result stays visible.
- **Award.** A person decides. The tool never awards.

**Audit log (append-only):** user and time; file hash; extracted text; model, prompt and criteria versions; every fact with its quote; every score; flags raised; each human edit with old value, new value and reason; the final decision.

## 4. Changing criteria

Criteria are versioned. An edit creates a new version and never rewrites the old one; every scoring run records the version it used.

- **Weights or thresholds changed:** rescore in code from stored facts. Instant, no AI cost.
- **A new or reworded criterion that needs new facts:** extract only those fields again; keep the rest.
- **Existing results** show "scored under v2, current v3". The reviewer chooses to re-run, both runs are kept, and a rank diff is shown. A recorded award stays tied to the version it used.
- **Pool-dependent scores** (price, timeline) are always recomputed together.

Only admins can edit, and every edit is logged.

## 5. Risks

| Risk | Safeguard |
|---|---|
| Wrong extraction | Verbatim quote verified by code; low-confidence and gate facts shown to the reviewer; unreadable or scanned files are flagged, not scored |
| Made-up facts | Schema allows "not stated"; a fact whose quote is not in the source is rejected; AI never computes a score (D's missing schedule stays missing) |
| Bias | AI does not score; names replaced by letters before extraction; only admin criteria count (roof reviews are noted, not scored); score distributions monitored |
| Manipulation (C) | Document text is delimited data and the prompt says to ignore instructions inside it; output limited to the schema so text cannot set a rank; keyword and AI checks plus hidden-text detection raise a flag; the attempt is logged and a human decides |
| Loopholes (B) | The gate requires a licence held by the bidder, not a promised subcontractor |
| Inconsistent price basis | Reviewer is told which bids state what their price includes |
| Cost | One extraction per file hash, cached; small model, short schema prompt, page limits; scoring is free arithmetic |

## Assumptions

- The note addressed to automated reviewers belongs to proposal C, because it sits directly after C's text.
- "Since 2021" counts as inside the 5-year window; "since 2020" is treated as partly outside, so C's install count is unverified.
- Flagged proposals (C and D) get no automatic rank and a null score, as in the brief's example; a provisional score is given in the reason.
- Eligibility also requires the price to be within the ceiling and any stated schedule to be within 16 weeks.
- Scoring rules are my defaults (experience bands, best-in-pool ratios for price and timeline, a four-item team checklist); the weights are the admin's, unchanged. Re-running with other weights and rules kept A first and E second.
