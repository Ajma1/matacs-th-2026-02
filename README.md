# MATACS-TH-2026-02: AI Proposal Triage Design

- **Name:** Muhammad Ajmal Malik
- **Reference:** MATACS-TH-2026-02
- **Time actually spent:** About 3 hours. This is more than the suggested 60 minutes because it includes reading the brief, reviewing the design and its calculations, and understanding the reasoning, not only writing it.

## How I used AI tools

I used Claude (Anthropic) heavily: it analysed the brief, designed the process, built the scoring calculations, ran the what-if tests and drafted every file in this repository. I then reviewed the design, the scores and the reasoning, and I agree with the result. In the interest of honesty, I did not find a flaw that I corrected myself; the corrections below were made while checking the AI's own output.

- A first draft described A's price as "within 3%" of the lowest eligible bid. When the arithmetic was checked (238,000 / 231,000 is 3.03% above), the wording was corrected to "about 3% above".
- A quick calculation script rounded D's provisional score as 76.2 while the spreadsheet showed 76.25; the figure was corrected to 76.3 everywhere so all files agree.
- A chart label that crossed a gridline and a clipped footnote were fixed after rendering.

## Files

- [WRITEUP.md](WRITEUP.md): answers to the five questions
- [diagram/process-flow.png](diagram/process-flow.png): process flow from upload to ranked output, showing AI steps, rule steps and human checkpoints
- [PROMPTS.md](PROMPTS.md): the extraction prompt and the reason-line prompt
- [ranking.json](ranking.json): expected ranking of proposals A to E

## Assumptions

- The note addressed to automated reviewers, found in the sample set, belongs to proposal C (it follows C's text and refers to Appendix C).
- "Since 2021" counts as inside the 5-year window; "since 2020" is treated as partly outside, so that bidder's install count is unverified.
- Flagged proposals (C and D) get no automatic rank and a null score, as in the brief's example; a provisional score appears in the reason line.
- Eligibility also requires the price to be within the ceiling and any stated schedule to be within 16 weeks.
- Scoring defaults are mine; the weights are the admin's, used unchanged. Re-running with other weights and rubric choices kept A first and E second.

No code or API keys are included; no prototype was built.
