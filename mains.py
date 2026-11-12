
import argparse
import asyncio
import os
import time
import uuid
import csv
import json
import re
from pathlib import Path
from collections import deque
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
import uvicorn
import httpx
from pypdf import PdfReader

PAPERS = {
    "attention_v7.pdf": "https://arxiv.org/pdf/1706.03762v7",
    "moshi_v1.pdf": "https://arxiv.org/pdf/2410.00037v1",
    "dynamic_chunking_v2.pdf": "https://arxiv.org/pdf/2507.07955v2"
}

DATA = Path("data")
PAPER_DIR = Path("papers")
CSV_FILE = DATA / "results.csv"

QUESTIONS = [
    "What is the role of attention in the Transformer architecture?",
    "How does multi-head attention work?",
    "What positional information is used by the Transformer?",
    "What is the main idea of the Moshi speech-text model?",
    "How does Moshi support real-time dialogue?",
    "What is dynamic chunking?",
    "How does hierarchical sequence modeling work?",
    "What are the main contributions of Attention Is All You Need?",
    "What latency measurements are discussed in Moshi?",
    "What datasets are used in the Transformer paper?",
    "What is the purpose of chunk boundaries?",
    "What limitations are discussed in the research papers?",
    "How does the Transformer differ from recurrent networks?",
    "What evidence supports dynamic chunking?",
    "Do the papers specify Groq API rate limits?"
]


def download_papers():
    PAPER_DIR.mkdir(exist_ok=True)

    for filename, url in PAPERS.items():
        path = PAPER_DIR / filename

        if path.exists() and path.stat().st_size > 1000:
            print("Already downloaded:", filename)
            continue

        print("Downloading:", filename)

        response = httpx.get(url, timeout=90, follow_redirects=True)
        response.raise_for_status()

        if not response.content.startswith(b"%PDF"):
            raise RuntimeError("Invalid PDF download: " + filename)

        path.write_bytes(response.content)
        print("Saved:", path)


def load_documents(chunk_size=350, overlap=60):
    documents = []

    if not PAPER_DIR.exists():
        raise RuntimeError("Run python main.py download first")

    for pdf in PAPER_DIR.glob("*.pdf"):
        reader = PdfReader(str(pdf))

        for page_number, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ""
            words = text.split()
            step = max(1, chunk_size - overlap)

            for start in range(0, len(words), step):
                chunk = " ".join(words[start:start + chunk_size])

                if len(chunk) > 80:
                    documents.append({
                        "paper": pdf.name,
                        "page": page_number,
                        "text": chunk
                    })

    if not documents:
        raise RuntimeError("No PDF text found")

    return documents


def retrieve(question, documents, top_k=4):
    query = set(re.findall(r"[a-z0-9]+", question.lower()))
    scored = []

    for doc in documents:
        terms = set(re.findall(r"[a-z0-9]+", doc["text"].lower()))
        score = len(query.intersection(terms))

        if score:
            scored.append((score, doc))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [doc for score, doc in scored[:top_k]]


def append_result(row):
    DATA.mkdir(exist_ok=True)
    exists = CSV_FILE.exists()

    with open(CSV_FILE, "a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(row.keys()))

        if not exists:
            writer.writeheader()

        writer.writerow(row)


class StandinServer:
    def __init__(self):
        self.app = FastAPI(title="The Relay Stand-in")
        self.recent = deque()
        self.count = 0
        self.active = 0
        self.daily = 0

        self.rpm = int(os.getenv("STANDIN_RPM", "60"))
        self.daily_limit = int(os.getenv("STANDIN_DAILY_REQUESTS", "10000"))
        self.fail_every = int(os.getenv("STANDIN_FAIL_EVERY", "0"))
        self.limit_every = int(os.getenv("STANDIN_RATE_LIMIT_EVERY", "0"))
        self.delay = int(os.getenv("STANDIN_BASE_DELAY_MS", "250")) / 1000

        self.app.get("/health")(self.health)
        self.app.post("/generate")(self.generate)

    async def health(self):
        return {"status": "running", "rpm": self.rpm}

    async def generate(self, request: Request):
        payload = await request.json()
        prompt = str(payload.get("prompt", ""))

        now = time.time()

        while self.recent and now - self.recent[0] >= 60:
            self.recent.popleft()

        self.count += 1
        self.daily += 1

        if self.daily > self.daily_limit:
            return JSONResponse(
                {"error": "Daily budget exhausted"},
                status_code=429,
                headers={"Retry-After": "3600"}
            )

        if len(self.recent) >= self.rpm:
            return JSONResponse(
                {"error": "RPM limit reached"},
                status_code=429,
                headers={"Retry-After": "60"}
            )

        self.recent.append(now)

        if self.limit_every and self.count % self.limit_every == 0:
            return JSONResponse({"error": "Injected rate limit"},
                                status_code=429)

        if self.fail_every and self.count % self.fail_every == 0:
            return JSONResponse({"error": "Injected failure"},
                                status_code=503)

        self.active += 1

        try:
            await asyncio.sleep(
                self.delay + max(0, self.active - 1) * 0.1
            )

            output = (
                "LOCAL STAND-IN RESPONSE. This is a simulation, "
                "not a real research answer. Prompt words: "
                + str(len(prompt.split()))
            )

            async def stream():
                words = output.split()

                for index in range(0, len(words), 5):
                    yield "data: " + " ".join(
                        words[index:index + 5]
                    ) + "\n\n"
                    await asyncio.sleep(0.04)

                yield "data: [DONE]\n\n"

            return StreamingResponse(
                stream(),
                media_type="text/event-stream"
            )

        finally:
            self.active = max(0, self.active - 1)


def start_standin():
    server = StandinServer()
    uvicorn.run(server.app, host="0.0.0.0", port=8765)


async def ask_question(question, backend="standin", documents=None):
    request_id = str(uuid.uuid4())
    started = time.perf_counter()
    first_token = ""

    if documents is None:
        documents = load_documents()

    evidence = retrieve(question, documents)

    if not evidence:
        answer = "The papers do not provide enough matching evidence."
        status = "no_evidence"
    elif backend == "standin":
        async with httpx.AsyncClient(timeout=60) as client:
            try:
                async with client.stream(
                    "POST",
                    "http://127.0.0.1:8765/generate",
                    json={"prompt": question}
                ) as response:
                    response.raise_for_status()
                    parts = []

                    async for line in response.aiter_lines():
                        if line.startswith("data:"):
                            value = line[5:].strip()

                            if value == "[DONE]":
                                break

                            if value:
                                if first_token == "":
                                    first_token = round(
                                        (time.perf_counter() - started) * 1000,
                                        2
                                    )
                                parts.append(value)

                    answer = " ".join(parts)
                    status = "ok"

            except Exception as error:
                answer = str(error)
                status = "error"

    else:
        from groq import AsyncGroq

        key = os.getenv("GROQ_API_KEY")

        if not key:
            raise RuntimeError("Set GROQ_API_KEY before using Groq")

        client = AsyncGroq(api_key=key)

        context = "\n".join(
            f"[{d['paper']}, page {d['page']}] {d['text']}"
            for d in evidence
        )

        try:
            stream = await client.chat.completions.create(
                model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Answer only from supplied evidence. "
                            "Cite claims as [filename.pdf, page N]. "
                            "Say when evidence is insufficient."
                        )
                    },
                    {
                        "role": "user",
                        "content": question + "\n\n" + context
                    }
                ],
                temperature=0,
                max_tokens=500,
                stream=True
            )

            parts = []

            async for chunk in stream:
                if chunk.choices:
                    text = chunk.choices[0].delta.content

                    if text:
                        if first_token == "":
                            first_token = round(
                                (time.perf_counter() - started) * 1000,
                                2
                            )

                        parts.append(text)

            answer = "".join(parts)
            status = "ok"

        except Exception as error:
            answer = str(error)
            status = "error"

    total = round((time.perf_counter() - started) * 1000, 2)

    row = {
        "request_id": request_id,
        "scenario": "single",
        "source": backend,
        "start_time": datetime.now(timezone.utc).isoformat(),
        "first_token_ms": first_token,
        "total_ms": total,
        "status": status,
        "retries": 0,
        "tokens_in": "",
        "tokens_out": "",
        "retrieval_setting": "lexical_chunk350_top4",
        "answer_grade": "not_manually_verified",
        "queue_wait_ms": 0,
        "rate_limit_headers": "{}"
    }

    append_result(row)

    print("\nQUESTION:", question)
    print("\nANSWER:", answer)
    print("\nMETRICS:", json.dumps(row, indent=2))


async def evaluate(backend):
    documents = load_documents()

    for question in QUESTIONS:
        await ask_question(question, backend, documents)


async def load_test(args):
    documents = load_documents()
    started = time.perf_counter()

    async def send(index):
        if args.scenario == "steady":
            await asyncio.sleep(index / max(args.rate, 0.1))
        elif args.scenario == "burst":
            await asyncio.sleep(index * 0.01)
        elif args.scenario in ("overload", "minute_halved"):
            await asyncio.sleep(index / max(args.rate, 0.1))
        elif args.scenario == "daily_exhausted":
            await asyncio.sleep(index / max(args.rate, 0.1))

        question = QUESTIONS[index % len(QUESTIONS)]
        await ask_question(question, args.backend, documents)

    await asyncio.gather(*[
        send(i) for i in range(args.requests)
    ])

    print(
        "\nCompleted", args.requests,
        "requests in", round(time.perf_counter() - started, 2), "seconds"
    )


def report():
    Path("reports").mkdir(exist_ok=True)

    content = """# The Relay Report

## 1. System Design
Describe the pipeline, routing, retrieval, generation and verification.

## 2. Real Service Limits
Record measured Groq RPM, TPM, RPD, TPD and concurrency.
Use actual dashboard/API evidence.

## 3. Stand-in Calibration
Record local delay, failures, rate limits and concurrency settings.

## 4. Load Test Results
Analyze data/results.csv for steady, burst and overload tests.

## 5. Retrieval Evaluation
Compare chunk sizes, overlap, top-k and answer correctness.

## 6. Naive Retriever Failure Modes
Discuss keyword mismatch, PDF extraction and chunk boundaries.

## 7. Vaani Feedback
Add actual feedback and resulting changes.

## 8. Assistant Collaboration
Describe planning, testing and debugging honestly.

Do not invent measurements or claim simulated results are real Groq results.
"""

    Path("reports/report.md").write_text(content, encoding="utf-8")
    print("Report template created.")


def main():
    parser = argparse.ArgumentParser(description="The Relay Pipeline")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("download")
    commands.add_parser("standin")
    commands.add_parser("report")
    commands.add_parser("benchmark-retrieval")

    ask = commands.add_parser("ask")
    ask.add_argument("question")
    ask.add_argument("--backend", choices=["groq", "standin"], default="standin")

    ev = commands.add_parser("evaluate")
    ev.add_argument("--backend", choices=["groq", "standin"], default="standin")

    load = commands.add_parser("load")
    load.add_argument("--backend", choices=["groq", "standin"], default="standin")
    load.add_argument("--scenario", choices=[
        "steady", "burst", "overload",
        "minute_halved", "daily_exhausted"
    ], default="steady")
    load.add_argument("--requests", type=int, default=20)
    load.add_argument("--rate", type=float, default=4)

    args = parser.parse_args()

    if args.command == "download":
        download_papers()

    elif args.command == "standin":
        start_standin()

    elif args.command == "ask":
        asyncio.run(ask_question(args.question, args.backend))

    elif args.command == "evaluate":
        asyncio.run(evaluate(args.backend))

    elif args.command == "load":
        asyncio.run(load_test(args))

    elif args.command == "report":
        report()

    elif args.command == "benchmark-retrieval":
        print("Use the three chunk-size settings in your retrieval evaluation.")
        print("This starter version does not generate a benchmark file.")


if __name__ == "__main__":
    main()
