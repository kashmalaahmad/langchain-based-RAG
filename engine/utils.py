import yaml
import pandas as pd
import json
from typing import List, Dict

def load_rules(path: str = "data/rules.yaml"):
    with open(path, "r", encoding="utf8") as f:
        rules = yaml.safe_load(f)
    return rules

def save_results_csv(results: List[Dict], outpath: str = "compliance_report.csv"):
    rows = []
    for r in results:
        rows.append({
            "rule_id": r.get("rule_id"),
            "rule_name": r.get("rule_name", ""),
            "status": r.get("status", ""),
            "confidence": r.get("confidence", r.get("confidence", "")),
            "evidence": " || ".join([ (e.get("text") + " @ " + e.get("source")) if isinstance(e, dict) else str(e) for e in r.get("evidence", []) ]),
            "recommended_corrections": " || ".join(r.get("recommended_corrections", [])),
            "top_score": r.get("_retrieval", {}).get("top_score", ""),
            "num_retrieved": r.get("_retrieval", {}).get("num_retrieved", "")
        })
    df = pd.DataFrame(rows)
    df.to_csv(outpath, index=False)
    print("Saved CSV to", outpath)

def save_results_markdown(results: List[Dict], outpath: str = "compliance_report.md"):
    lines = ["# Compliance Report", "", "| Rule ID | Rule Name | Status | Confidence | Evidence | Recommendations |", "|---|---|---|---|---|---|"]
    for r in results:
        evidence_md = "<br/>".join([ (e.get("text") + " — " + e.get("source")) if isinstance(e, dict) else str(e) for e in r.get("evidence", []) ])
        recs_md = "<br/>".join(r.get("recommended_corrections", []))
        lines.append("|{}|{}|{}|{}|{}|{}|".format(
            r.get("rule_id"),
            r.get("rule_name"),
            r.get("status"),
            r.get("confidence", ""),
            evidence_md,
            recs_md
        ))
    content = "\n".join(lines)
    with open(outpath, "w", encoding="utf8") as f:
        f.write(content)
    print("Saved Markdown to", outpath)

def save_raw_json(results: List[Dict], outpath: str = "compliance_report.json"):
    with open(outpath, "w", encoding="utf8") as f:
        json.dump(results, f, indent=2)
    print("Saved raw JSON to", outpath)
