#!/usr/bin/env python3
"""Prototype of the AI proposal triage flow (MATACS-TH-2026-02).

AI reads, code decides, a human awards:
  - AI (live mode only): extracts facts with quotes using the prompt in ../PROMPTS.md.
  - Code: verifies quotes, scans for injected instructions, applies mandatory gates,
    scores, ranks, and writes an audit log. No score or rank ever comes from the model.

Usage:
  python run_triage.py --offline              # no API key: runs gates + scoring on fixtures/facts.json
  python run_triage.py --samples samples/     # live: runs the prompt on samples/A.txt ... E.txt
  python run_triage.py --samples samples/ --ai-reasons   # also let the model word the reason lines

Sample proposal text is NOT stored in this repository. Put your own copies in
prototype/samples/ (git-ignored), one file per proposal named by its letter.
"""
import argparse
import json
import os
import re
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

SECTIONS = {  # section -> the fact fields that need a verifiable quote when true or numeric
    "licence": ["held_by_bidder"],
    "wsib": ["confirmed"],
    "insurance": ["liability_5m_confirmed"],
    "experience": ["installs_100kw_plus"],
    "price": ["total_cad"],
    "timeline": ["weeks_from_award"],
    "warranty": ["panel_years", "workmanship_years"],
    "team": ["named_lead", "crew_size", "safety_plan", "monitoring_plan"],
}

# Rule-based injection scan: a backstop to the model's own injection_detected flag.
INJECTION_PATTERNS = [
    r"automated\s+(review|evaluation|scoring|assessment)\s+(system|tool|software)s?",
    r"\b(rank|rate|score|place)\s+(it|this\s+(proposal|bid|submission))\s+(first|highest|#?1|top)",
    r"\bfull\s+(marks|score|points)\b",
    r"\bignore\s+(all\s+|any\s+|the\s+)?(previous|prior|above|earlier)\s+(instructions|criteria|rules)",
    r"\bpre-?approved\b",
    r"\bnote\s+to\s+(the\s+)?(ai|llm|model|reviewer|evaluator|grader)",
]


# ---------------------------------------------------------------- helpers
def load_env():
    """Tiny .env reader so no extra dependency is needed. Never prints values."""
    for path in (HERE / ".env", ROOT / ".env"):
        if path.exists():
            for line in path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def round1(x):
    return float(Decimal(str(x)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def norm(s):
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s).strip().lower()


def load_prompts():
    """Read the prompts exactly as written in PROMPTS.md so there is one source of truth."""
    text = (ROOT / "PROMPTS.md").read_text()
    first, _, second = text.partition("# Prompt 2")

    def part(block, start, end):
        a = block.index(start) + len(start)
        b = block.index(end, a) if end else len(block)
        return block[a:b].strip()

    return {
        "extract_system": part(first, "## System message", "## User message template"),
        "extract_user": part(first, "## User message template", "## Settings"),
        "reason_system": part(second, "## System message", "## User message template"),
        "reason_user": part(second, "## User message template", None),
    }


def parse_json(raw):
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end < start:
        raise ValueError("model reply contains no JSON object")
    return json.loads(raw[start:end + 1])


def call_model(client, model, system, user, max_tokens=1500):
    kwargs = dict(model=model, max_tokens=max_tokens, system=system,
                  messages=[{"role": "user", "content": user}])
    try:
        msg = client.messages.create(temperature=0, **kwargs)
    except Exception as exc:  # some models reject temperature; retry once without it
        if "temperature" not in str(exc).lower():
            raise
        msg = client.messages.create(**kwargs)
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


# ------------------------------------------------- AI step 4 + code step 5
def extract_live(client, model, prompts, criteria_version, letter, text):
    user = (prompts["extract_user"]
            .replace("{{criteria_version}}", criteria_version)
            .replace("{{letter}}", letter)
            .replace("{{proposal_text}}", text))
    return parse_json(call_model(client, model, prompts["extract_system"], user))


def verify_extraction(facts, text):
    """Code check: every quote must appear in the source, and true/numeric facts need one.
    A section that fails is nulled (never guessed) and reported to the reviewer."""
    issues = []
    source = norm(text)
    for section, fields in SECTIONS.items():
        sec = facts.get(section) or {}
        quote = sec.get("quote")
        snippets = [norm(q) for q in str(quote).split("|") if q.strip()] if quote else []
        needs_quote = any(sec.get(f) not in (None, False) for f in fields)
        if needs_quote and not snippets:
            issues.append(f"{section}: fact stated without a quote; set to not stated")
            bad = True
        elif any(q not in source for q in snippets):
            issues.append(f"{section}: quote not found in the source; set to not stated")
            bad = True
        else:
            bad = False
        if bad:
            for f in fields:
                sec[f] = None
        facts[section] = sec
    inj = facts.get("injection_quote")
    if inj and norm(inj) not in source:
        issues.append("injection_quote not found in the source (flag kept anyway)")
    return facts, issues


def scan_injection(text):
    return [p for p in INJECTION_PATTERNS if re.search(p, text, re.IGNORECASE)]


# ------------------------------------------------------------ code steps
def band_score(count, bands):
    score = 0
    for minimum, points in bands:
        if count >= minimum:
            score = points
    return score


def get(facts, section, field):
    return (facts.get(section) or {}).get(field)


def gate(facts, c):
    """Return (eligible, missing, reasons). False = fails a mandatory criterion; None = not stated."""
    fail, missing = [], []
    for label, value in (("licence held by the bidder", get(facts, "licence", "held_by_bidder")),
                         ("WSIB clearance", get(facts, "wsib", "confirmed")),
                         ("$5M liability insurance", get(facts, "insurance", "liability_5m_confirmed"))):
        if value is False:
            fail.append(f"fails mandatory criterion: {label}")
        elif value is None:
            missing.append(f"{label} not stated")
    price, weeks = get(facts, "price", "total_cad"), get(facts, "timeline", "weeks_from_award")
    if price is None:
        missing.append("price not stated")
    elif price > c["budget_ceiling_cad"]:
        fail.append("price is over the budget ceiling")
    if weeks is None:
        missing.append("schedule not stated, so the week limit cannot be confirmed")
    elif weeks > c["max_weeks"]:
        fail.append("schedule is over the week limit")
    return (not fail), missing, fail


def triage(all_facts, c, injection_hits=None):
    injection_hits = injection_hits or {}
    records = {}
    for facts in all_facts:
        pid = facts["proposal_id"]
        ok, missing, fail = gate(facts, c)
        injected = bool(facts.get("injection_detected")) or bool(injection_hits.get(pid))
        records[pid] = {"facts": facts, "eligible": ok, "missing": missing, "fail": fail,
                        "injection": injected, "scores": None, "total": None}
    pool = [r for r in records.values() if r["eligible"]]
    prices = [get(r["facts"], "price", "total_cad") for r in pool if get(r["facts"], "price", "total_cad")]
    weeks = [get(r["facts"], "timeline", "weeks_from_award") for r in pool if get(r["facts"], "timeline", "weeks_from_award")]
    panel = [get(r["facts"], "warranty", "panel_years") or 0 for r in pool]
    work = [get(r["facts"], "warranty", "workmanship_years") or 0 for r in pool]
    best_price, best_weeks = min(prices, default=None), min(weeks, default=None)
    best_panel, best_work = max(panel, default=0), max(work, default=0)
    split = c["warranty_split"]
    for r in pool:
        f = r["facts"]
        p, w = get(f, "price", "total_cad"), get(f, "timeline", "weeks_from_award")
        wp, ww = get(f, "warranty", "panel_years") or 0, get(f, "warranty", "workmanship_years") or 0
        team = sum([bool(get(f, "team", "named_lead")), bool(get(f, "team", "crew_size")),
                    bool(get(f, "team", "safety_plan")), bool(get(f, "team", "monitoring_plan"))])
        s = {
            "experience": band_score(get(f, "experience", "installs_100kw_plus") or 0, c["experience_bands"]),
            "price": best_price / p * 100 if p and best_price else 0,
            "timeline": best_weeks / w * 100 if w and best_weeks else 0,
            "warranty": (split["panel"] * (wp / best_panel * 100 if best_panel else 0)
                         + split["workmanship"] * (ww / best_work * 100 if best_work else 0)),
            "team": c["team_points_each"] * team,
        }
        r["scores"] = s
        r["total"] = sum(c["weights"][k] * s[k] for k in c["weights"])
        r["status"] = "flagged" if (r["injection"] or r["missing"]) else "ranked"
    for r in records.values():
        if not r["eligible"]:
            r["status"] = "ineligible"
    ranked = sorted((pid for pid, r in records.items() if r["status"] == "ranked"),
                    key=lambda k: (-records[k]["total"], -records[k]["scores"]["experience"],
                                   get(records[k]["facts"], "price", "total_cad") or 0))
    for i, pid in enumerate(ranked, 1):
        records[pid]["rank"] = i
    for r in records.values():
        r.setdefault("rank", None)
    return records


def template_reason(pid, r):
    if r["status"] == "ineligible":
        return "Ineligible: " + "; ".join(r["fail"]) + "."
    if r["status"] == "flagged":
        why = []
        if r["injection"]:
            why.append("text addressed to automated reviewers was ignored")
        why += r["missing"]
        return f"Flagged for a human: {'; '.join(why)}. Provisional score {round1(r['total'])}."
    f = r["facts"]
    return (f"Rank {r['rank']} ({round1(r['total'])}): passes both gates; "
            f"{get(f, 'experience', 'installs_100kw_plus')} qualifying installs, "
            f"{get(f, 'timeline', 'weeks_from_award')} weeks, price {get(f, 'price', 'total_cad'):,.0f} CAD.")


def ai_reason(client, model, prompts, pid, r):
    breakdown = {"proposal": pid, "status": r["status"], "rank": r["rank"],
                 "total": round1(r["total"]) if r["total"] is not None else None,
                 "criterion_scores": {k: round1(v) for k, v in (r["scores"] or {}).items()},
                 "problems": r["fail"] + r["missing"] + (["injected instructions ignored"] if r["injection"] else [])}
    user = prompts["reason_user"].replace("{{score_breakdown_json}}", json.dumps(breakdown, indent=2))
    return call_model(client, model, prompts["reason_system"], user, max_tokens=200).strip()


# ------------------------------------------------------------------ main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--samples", help="folder with A.txt ... E.txt (live mode)")
    ap.add_argument("--offline", action="store_true", help="use fixtures/facts.json; no API call")
    ap.add_argument("--criteria", default=str(HERE / "criteria.json"))
    ap.add_argument("--out", default=str(HERE / "output"))
    ap.add_argument("--model", default=None)
    ap.add_argument("--ai-reasons", action="store_true", help="let the model word the reason lines")
    args = ap.parse_args(argv)
    if not args.offline and not args.samples:
        ap.error("give --samples <folder> for a live run, or --offline")

    load_env()
    c = json.loads(Path(args.criteria).read_text())
    prompts = load_prompts()
    audit = {"criteria_version": c["version"], "mode": "offline" if args.offline else "live", "proposals": {}}
    injection_hits, client, model = {}, None, args.model or os.environ.get("MODEL", "claude-sonnet-5-5")

    if args.offline:
        all_facts = json.loads((HERE / "fixtures" / "facts.json").read_text())["proposals"]
        print("Offline mode: using hand-built facts; quote verification and AI steps are skipped.\n")
    else:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            sys.exit("ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key.")
        try:
            import anthropic
        except ImportError:
            sys.exit("Install the SDK first: pip install -r prototype/requirements.txt")
        client = anthropic.Anthropic()
        files = sorted(Path(args.samples).glob("*.txt"))
        if not files:
            sys.exit(f"No .txt files found in {args.samples}")
        all_facts = []
        for path in files:
            letter, text = path.stem.upper(), path.read_text()
            facts = extract_live(client, model, prompts, c["version"], letter, text)
            facts["proposal_id"] = letter
            facts, issues = verify_extraction(facts, text)
            injection_hits[letter] = scan_injection(text)
            audit["proposals"][letter] = {"extraction_issues": issues, "regex_injection_hits": injection_hits[letter],
                                          "model": model, "extracted": facts}
            all_facts.append(facts)

    records = triage(all_facts, c, injection_hits)
    out = []
    for pid in sorted(records):
        r = records[pid]
        reason = ai_reason(client, model, prompts, pid, r) if (client and args.ai_reasons) else template_reason(pid, r)
        out.append({"proposal": pid, "rank": r["rank"], "status": r["status"],
                    "score": round1(r["total"]) if r["status"] == "ranked" else None, "reason": reason})
        audit["proposals"].setdefault(pid, {})["scores"] = r["scores"]
        audit["proposals"][pid]["total"] = r["total"]
        audit["proposals"][pid]["status"] = r["status"]

    print(f"{'Proposal':<9}{'Status':<12}{'Rank':<6}{'Score':<8}Reason")
    for row in sorted(out, key=lambda x: (x["rank"] is None, x["rank"] or 0, x["proposal"])):
        score = "-" if row["score"] is None else f"{row['score']:.1f}"
        print(f"{row['proposal']:<9}{row['status']:<12}{str(row['rank'] or '-'):<6}{score:<8}{row['reason']}")

    Path(args.out).mkdir(parents=True, exist_ok=True)
    (Path(args.out) / "ranking_generated.json").write_text(json.dumps(out, indent=2) + "\n")
    (Path(args.out) / "audit_log.json").write_text(json.dumps(audit, indent=2, default=str) + "\n")
    print(f"\nWrote {args.out}/ranking_generated.json and audit_log.json (git-ignored).")
    return out


if __name__ == "__main__":
    main()
