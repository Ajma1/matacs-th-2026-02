# MATACS-TH-2026-02: AI Proposal Triage Design

- **Name:** Muhammad Ajmal Malik
- **Reference:** MATACS-TH-2026-02
- **Time actually spent:** About 3 hours. This is more than the suggested 60 minutes because it includes reading the brief, reviewing the design and its calculations, and understanding the reasoning, not only writing it.

## How I used AI tools

I used Claude (Anthropic) to analyse the brief, design the process, build the scoring calculations and draft every file here, and I reviewed the design, scores and reasoning and agree with the result. I did not find a flaw of my own to correct, so the corrections I can report were made while checking the AI's output: it first described A's price as "within 3%" of the lowest eligible bid, and checking the arithmetic (3.03% above) corrected it to "about 3% above". It also reported D's provisional score as 76.2 from a rounding quirk in a script while the spreadsheet showed 76.25, which was corrected to 76.3 everywhere.

## Files

- [WRITEUP.md](WRITEUP.md): answers to the five questions
- [diagram/process-flow.png](diagram/process-flow.png): process flow from upload to ranked output, showing AI steps, rule steps and human checkpoints
- [PROMPTS.md](PROMPTS.md): the extraction prompt and the reason-line prompt
- [ranking.json](ranking.json): expected ranking of proposals A to E
- [prototype/](prototype/README.md): optional script that runs the prompt, then gates, scores and ranks in code; `.env.example` is provided and no key is committed

## Assumptions

Stated in full at the end of [WRITEUP.md](WRITEUP.md).
