# The Relay — Research Paper Assistant and Load-Test Mini Project

A runnable Python starter implementation for the assignment. It includes:
- Exact-version arXiv PDF download script.
- PDF extraction with page-aware chunks and lexical retrieval.
- Multi-step question → retrieval → decision → answer → citation verification pipeline.
- Groq streaming backend and a local controllable stand-in HTTP service.
- Bounded concurrency, simple retry policy, load scenarios, and per-request `results.csv`.
- A 15-question evaluation set and report-table generator.

## Important honesty note
This is an engineering starter, not proof of measured results. Run the commands yourself.
Do not claim Groq RPM/TPM/RPD/TPD or latency values unless observed in your own Groq console/API responses.
The stand-in is a configurable approximation, not a faithful model of Groq infrastructure.
A daily-budget test is simulated locally; do not intentionally exhaust your real daily quota.
The evaluation grader is deliberately conservative and partly rule-based; manually review its grades before reporting answer quality.

## 1. Setup in GitHub Codespaces
Open the repository in Codespaces, then in the terminal:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

On Windows PowerShell use `.venv\\Scripts\\Activate.ps1` instead.
Set `GROQ_API_KEY` in the Codespaces secret named `GROQ_API_KEY`, or in `.env` (never commit `.env`).
Set `BACKEND=standin` for safe initial tests. Use `BACKEND=groq` only for a small number of real calls.

## 2. Download the exact paper versions
```bash
python download_papers.py
```
The script downloads:
- https://arxiv.org/pdf/1706.03762v7
- https://arxiv.org/pdf/2410.00037v1
- https://arxiv.org/pdf/2507.07955v2

## 3. Build the local index
```bash
python -m app.cli index
```

## 4. Start the stand-in server (terminal 1)
```bash
uvicorn app.standin_server:app --host 0.0.0.0 --port 8000
```

## 5. Run one request (terminal 2)
```bash
python -m app.cli ask "What is the role of multi-head attention in the Transformer?"
```

## 6. Run evaluation questions
```bash
python -m app.cli evaluate --backend standin
```
This creates `data/results.csv` and `data/evaluation_summary.json`.
The stand-in produces deterministic demo responses and is not an LLM. For quality evaluation, use `--backend groq` with a few carefully reviewed questions after confirming your account limits.

## 7. Run load scenarios
```bash
python -m app.cli load --backend standin --scenario steady --requests 20 --rate 4
python -m app.cli load --backend standin --scenario burst --requests 30 --rate 15
python -m app.cli load --backend standin --scenario overload --requests 60 --rate 30
python -m app.cli load --backend standin --scenario minute_halved --requests 20 --rate 8
python -m app.cli load --backend standin --scenario daily_exhausted --requests 20 --rate 5
```
Each command appends one row per request to `data/results.csv`. For `daily_exhausted`, a local simulated daily budget is used.

## 8. Groq measurements
Set `BACKEND=groq` in `.env` or pass `--backend groq`.
```bash
python -m app.cli ask "What does the Moshi paper say about real-time dialogue?"
python -m app.cli load --backend groq --scenario steady --requests 5 --rate 1
```
Start small. Record plan/model limits from the current Groq console and API response headers. The script records response headers when available. A free-tier daily quota can be shared with your other use.

## 9. Report tables
```bash
python -m app.cli report
```
This generates `reports/generated_tables.md` from the CSV. The two-page report still needs your interpretation and honest answers for unmeasured values.

## CSV columns
`request_id,scenario,source,start_time,first_token_ms,total_ms,status,retries,tokens_in,tokens_out,retrieval_setting,answer_grade`

## Known limitations to discuss
1. Lexical retrieval (TF-IDF-like token overlap) is not semantic embedding retrieval.
2. Citation checking verifies that cited paper/page references exist and that cited text overlaps; it cannot prove every claim is entailed.
3. Stand-in timing and limits are synthetic and only approximate observed service behavior.
4. Token counts for Groq are provider-reported where available; stand-in token counts are estimates.
5. A local daily-budget counter resets when the process restarts; it is a demonstration, not durable distributed accounting.
