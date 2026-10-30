# Prototype (optional)

A small script that runs the extraction prompt from [PROMPTS.md](../PROMPTS.md) on the sample proposals, then applies the gates, scoring and ranking in plain code. It follows the same rule as the design: **AI reads, code decides, a human awards.** No score or rank ever comes from the model.

## What is AI and what is code

| Step | Who |
|---|---|
| Extract facts with a quote per fact | AI (prompt 1 in PROMPTS.md, temperature 0) |
| Check each quote exists in the source; null any fact without one | Code |
| Scan for instructions aimed at reviewers (backstop to the model's own flag) | Code (regex) |
| Mandatory gates, hard limits, scoring, ranking, status | Code, driven by `criteria.json` |
| One-line reason | Template by default; AI only with `--ai-reasons` (prompt 2) |
| Audit log (facts, quotes, issues, scores, versions) | Code, written to `output/audit_log.json` |

## Run it

```bash
pip install -r prototype/requirements.txt        # only needed for live runs
cp .env.example .env                              # then add your own ANTHROPIC_API_KEY
python prototype/run_triage.py --offline          # no key needed: gates + scoring on hand-built facts
python prototype/run_triage.py --samples prototype/samples/
python prototype/run_triage.py --samples prototype/samples/ --ai-reasons
python -m unittest prototype/test_prototype.py    # 10 tests, no key needed
```

## About the samples

The brief says not to copy the sample proposal text into the repository, so **the text is not here**. For a live run, put one text file per proposal in `prototype/samples/` named by letter (`A.txt` to `E.txt`). That folder is git-ignored, as is `prototype/output/` (the audit log contains quotes from the samples).

`fixtures/facts.json` holds facts only (numbers and yes/no values, no wording or quotes) so the scoring code can be run and tested offline. In offline mode the quote check and the AI steps are skipped.

## Admin criteria are not hard-coded

Weights, the budget ceiling, the week limit and the scoring bands live in `criteria.json`. Editing that file and re-running rescores everything without any AI call.

## What was and was not tested

- Offline run: reproduces `ranking.json` exactly (A first at 98.0, E second at 91.7, B ineligible, C and D flagged).
- Live path: tested with a fake model client and invented proposal text, covering a made-up quote being rejected and an injected instruction being flagged even when the model misses it. **It has not been run against the real API**, because no key was available when this was written.
- Known limit: one quote per section is verified, so a section's quote can prove a snippet exists but not that every fact in the section is covered. A production version would use one quote per fact.
