import csv
from pathlib import Path
import pandas as pd

FIELDS = [
    "request_id", "scenario", "source", "start_time", "first_token_ms",
    "total_ms", "status", "retries", "tokens_in", "tokens_out",
    "retrieval_setting", "answer_grade", "queue_wait_ms"
]
CSV_PATH = Path("data/results.csv")

def append_record(record):
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    exists = CSV_PATH.exists()
    with CSV_PATH.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        writer.writerow(record)

def generate_report_tables():
    if not CSV_PATH.exists():
        print("No results.csv yet.")
        return
    df = pd.read_csv(CSV_PATH)
    out = ["# Generated results summary", "", "Generated directly from data/results.csv. Check the raw rows."]
    for scenario, group in df.groupby("scenario"):
        out += [f"## {scenario}", f"- Requests: {len(group)}",
                f"- Source(s): {', '.join(sorted(group.source.dropna().unique()))}",
                f"- First token p50/p95/p99 (ms): {group.first_token_ms.dropna().quantile(.5):.1f} / {group.first_token_ms.dropna().quantile(.95):.1f} / {group.first_token_ms.dropna().quantile(.99):.1f}" if group.first_token_ms.notna().any() else "- First token: not measured",
                f"- Total p50/p95/p99 (ms): {group.total_ms.quantile(.5):.1f} / {group.total_ms.quantile(.95):.1f} / {group.total_ms.quantile(.99):.1f}",
                f"- Success/rate-limited/timeout-error: {(group.status=='ok').mean()*100:.1f}% / {(group.status=='rate_limited').mean()*100:.1f}% / {group.status.isin(['timeout','error']).mean()*100:.1f}%",
                f"- Mean retries/request: {group.retries.mean():.2f}",
                f"- Mean tokens/answer: {(group.tokens_in+group.tokens_out).mean():.1f}", ""]
    Path("reports").mkdir(exist_ok=True)
    Path("reports/generated_tables.md").write_text("\n".join(out), encoding="utf-8")
    print("Wrote reports/generated_tables.md")
