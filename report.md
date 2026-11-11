# The Relay — report draft

> Replace every placeholder with measured values from `data/results.csv` and your own Groq console/API observations. Never invent measurements.

## 1 What I built and why
I built a Python research-paper assistant with page-aware PDF retrieval, a model-provider interface, a controllable stand-in service, bounded concurrency, retry handling, citation checks, and per-request CSV logging. The main design decision was to separate the pipeline from the provider so the same workflow can be tested against Groq and a local simulator.

## 2 The real service and my stand-in
Groq model: [fill in]. Account plan: [fill in]. Observed RPM: [measured/not measured]. TPM: [measured/not measured]. RPD: [measured/not measured]. TPD: [measured/not measured]. Record actual response headers and status codes. The stand-in adds configurable delay, concurrency slowdown, injected 429/503 responses, and chunked streaming. It differs most because it does not reproduce provider scheduling, model compute variability, tokenization, or real quota accounting.

## 3 Results
Copy the generated values from `reports/generated_tables.md`. State request counts and p50/p95/p99. If a scenario was not run, say not measured. Answer quality must be manually checked on at least 15 questions.

## 4 Where the time goes
Choose one slow request. Use recorded queue wait, provider-call duration, and retry timestamps/logs. The current starter logs queue wait and total time; extend it to log separate model-call and retry durations before making a detailed claim.

## 5 When a limit is hit
Describe actual observed Groq 429 behavior and the local daily-budget simulation separately. Do not claim a daily quota response unless observed.

## Retrieval: quality versus cost
Compare at least three chunk/retrieval settings. Current starter supports changing chunk_words and k in `app/retrieval.py` / `app/pipeline.py`; run and review each setting separately.

## How this library will mislead a naive retriever
1. Related technical terms occur across papers but mean different things; e.g. “chunk” in a speech/dialogue context versus hierarchical sequence modeling.
2. A paper's abstract may repeat a term without providing the detailed method; e.g. asking for implementation-level settings based only on an abstract match.
3. A question may ask for external service limits not covered by these papers; e.g. “What is Groq's free-tier daily quota?” The correct answer is that this library does not state it.

## 6 Retries
State the retry count, retryable errors, delay, and one measured example where retrying increased queueing or total latency.

## 7 What the person sees
At daily budget exhaustion, return a clear temporary-unavailable message and explain when service may resume if known. Do not fabricate a reset time.

## 8 What I'm unsure about, what I left out, what I learned
Least certain assumption: [fill in]. Two deliberately omitted features: [fill in]. New learning: [explain in your own words].

## Your feedback on Vaani
Visit https://www.vaani.dev/ yourself. Write what stood out, what confused you, and one change you would make.

## How I worked with the assistant
Attach the actual exported conversation or prompts. Identify three prompts that mattered, one assistant error you caught, one decision you overruled, and what is distinctly your work.
