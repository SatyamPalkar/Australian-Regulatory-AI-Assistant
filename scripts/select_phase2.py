"""Select the serving candidate using development proxies only, before test runs."""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reg_assistant.core import write_json
from reg_assistant.experiments import verify_phase2


def main():
    verify_phase2()
    destination = ROOT / "reports/phase2-selection.json"
    if destination.exists():
        raise SystemExit("Selection already recorded; preserve it")
    old = json.loads((ROOT / "reports/phase2-dev-v1-explain.json").read_text())["metrics"]
    new = json.loads((ROOT / "reports/phase2-dev-v2-explain.json").read_text())["metrics"]
    selected = (new["structured_explanation_rate"] > old["structured_explanation_rate"]
                and new["qualification_term_coverage"] > old["qualification_term_coverage"]
                and new["expected_source_cited_rate"] >= old["expected_source_cited_rate"]
                and new["unsupported_abstention_rate"] >= old["unsupported_abstention_rate"])
    write_json(destination, {"selected_mode": "v2-explain" if selected else "v1-explain",
               "automated_proxy_candidate": "v2-explain" if selected else "v1-explain",
               "serving_mode": "v1-concise", "serving_adapter": "adapters/consumer-law", "serving_answer_style": "concise",
               "development_review_veto": "reports/phase2-development-review.json",
               "serving_decision_basis": "Source review is required before promotion. Keep original concise standalone answers and use fresh source wording for dependent follow-ups; explanatory generation remains experimental.",
               "adapter": "adapters/explanatory-v2-selected" if selected else "adapters/consumer-law",
               "answer_style": "explain", "created_at": datetime.now(timezone.utc).isoformat(),
               "basis": "Development-only improvement in explanation structure and qualification keywords, without lower source citation or unsupported abstention. These proxies do not establish factual accuracy. Test reports were not consulted.",
               "development_metrics": {"v1-explain": old, "v2-explain": new}})
    print("Selected", "v2-explain" if selected else "v1-explain", "using development reports")


if __name__ == "__main__":
    main()
