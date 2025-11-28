import argparse
import os
from engine.utils import load_rules, save_results_csv, save_results_markdown, save_raw_json
from rag.rag_checker import RAGComplianceChecker
from dotenv import load_dotenv
load_dotenv(override=True)


def run(chroma_dir: str = "vector_db/chroma", top_k: int = 6, rules_path: str = "data/rules.yaml", outdir: str = "."):
    print("Loading rules...")
    rules = load_rules(rules_path)
    print(f"Loaded {len(rules)} rules.")

    print("Initializing RAGComplianceChecker...")
    checker = RAGComplianceChecker(chroma_dir=chroma_dir)

    all_results = []
    for rule in rules:
        print(f"Checking {rule.get('id')} - {rule.get('name')} ...")
        res = checker.check_rule(rule, top_k=top_k)
        res["rule_id"] = res.get("rule_id") or rule.get("id")
        res["rule_name"] = rule.get("name")
        if "evidence" not in res:
            res["evidence"] = []
        if "recommended_corrections" not in res:
            res["recommended_corrections"] = []
        all_results.append(res)

    os.makedirs(outdir, exist_ok=True)
    csv_path = os.path.join(outdir, "compliance_report.csv")
    md_path = os.path.join(outdir, "compliance_report.md")
    json_path = os.path.join(outdir, "compliance_report.json")

    save_results_csv(all_results, outpath=csv_path)
    save_results_markdown(all_results, outpath=md_path)
    save_raw_json(all_results, outpath=json_path)
    print("All done. Reports saved in:", outdir)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--chroma_dir", default="vector_db/chroma")
    parser.add_argument("--top_k", type=int, default=6)
    parser.add_argument("--rules_path", default="data/rules.yaml")
    parser.add_argument("--outdir", default=".")
    args = parser.parse_args()
    run(chroma_dir=args.chroma_dir, top_k=args.top_k, rules_path=args.rules_path, outdir=args.outdir)
