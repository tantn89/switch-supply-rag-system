"""Run all 10 evaluation questions + 3 bonus and print a summary table.

Usage (inside container or with backend running):
    python -m app.scripts.run_eval
"""
from __future__ import annotations

import json
import os
import sys
import time
from urllib import request as urlrequest

API = os.environ.get("EVAL_API", "http://localhost:8000")

QUESTIONS = [
    ("Q1", "What is the contact email for ACME Supply Co?"),
    ("Q2", "How many units of SKU-LED-100 are currently in stock?"),
    ("Q3", "What is the unit price for SKU-LED-200 in the Q1 catalog?"),
    ("Q4", "What are the certifications for SKU-LED-100 according to the product specifications?"),
    ("Q5", "Which products are below their reorder level? List the product name, current stock, reorder level, and the supplier's name."),
    ("Q6", "What is the total value of all pending purchase orders?"),
    ("Q7", "Compare the catalog price vs the PO price for SKU-LED-100. Is there a discount, and if so, what percentage?"),
    ("Q8", "Extract the invoice total from the scanned invoice image and tell me which PO number it corresponds to. Does the invoice total match the PO total in the database?"),
    ("Q9", "Show me all Australian vendors who supply products that are currently below 100 units in stock. For each vendor, list their contact email and which products they supply that are low stock."),
    ("Q10", "What is the shipping tracking number for PO-2847?"),
    ("B1", "Show me the trend of purchase order values over time. Which month had the highest total order value?"),
    ("B2", "Which vendor has the most products listed in the catalog? Compare their average unit prices."),
    ("B3", "Based on current stock levels and reorder points, which products should I prioritize ordering this week?"),
]


def ask(question: str) -> dict:
    body = json.dumps({"message": question}).encode()
    req = urlrequest.Request(
        f"{API}/chat/sync",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    with urlrequest.urlopen(req, timeout=120) as r:
        data = json.loads(r.read())
    data["_latency_s"] = round(time.time() - t0, 2)
    return data


def main() -> int:
    results = []
    for qid, q in QUESTIONS:
        print(f"\n{'='*70}\n{qid}: {q}\n{'='*70}")
        try:
            r = ask(q)
            results.append((qid, q, r))
            print(f"ROUTE: {r['route']['sources']} | sql={r['route'].get('sql_query')}")
            print(f"REASONING: {r['route']['reasoning']}")
            print(f"CITATIONS: {[c['source_id'] for c in r['citations']]}")
            print(f"CONFIDENCE: {r['confidence']}  LATENCY: {r['_latency_s']}s")
            print(f"ANSWER:\n{r['answer']}")
        except Exception as e:
            print(f"FAILED: {e}")
            results.append((qid, q, {"error": str(e)}))

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for qid, q, r in results:
        if "error" in r:
            print(f"{qid}: ERROR {r['error']}")
        else:
            print(
                f"{qid}: confidence={r['confidence']:8s} "
                f"latency={r['_latency_s']:>5}s "
                f"sources={','.join(r['route']['sources']) or '(none)'}"
            )

    # Persist for later inclusion in TEST_RESULTS.md.
    out_path = os.environ.get("EVAL_OUT", "/tmp/eval_results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nFull results saved to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
