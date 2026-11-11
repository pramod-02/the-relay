import argparse
import asyncio
import json
import time
import uuid
from pathlib import Path
from .pipeline import RelayPipeline
from .metrics import append_record, generate_report_tables

QUESTIONS = [
"What is the role of attention in the Transformer architecture?",
"How does multi-head attention differ from a single attention operation?",
"What positional information is used by the Transformer?",
"What does the Moshi paper describe as its approach to real-time dialogue?",
"What components are described in the Moshi system?",
"What is the main idea of dynamic chunking in the hierarchical sequence modeling paper?",
"How does the dynamic chunking paper describe chunk boundaries?",
"What datasets or benchmarks are reported in the Attention Is All You Need paper?",
"What latency measurements does the Moshi paper report?",
"What exact Groq free-tier daily token quota is stated in these three papers?",
"Do the three papers specify a recommended production retry policy?",
"Which of the papers compares Transformer attention with recurrent neural networks?",
"Do the papers give a numerical limit for concurrent API requests?",
"What evidence does the dynamic chunking paper provide for its method?",
"Do the papers explain how to avoid all hallucinations in a deployed assistant?"
]

async def run_one(question, backend, scenario):
    pipeline = RelayPipeline(backend=backend)
    result = await pipeline.answer(question, scenario=scenario)
    append_record(result["record"])
    print("\nQUESTION:", question)
    print("ANSWER:", result["answer"][:1500])
    print("RECORD:", json.dumps(result["record"], ensure_ascii=False))
    return result

async def load_run(args):
    sem = asyncio.Semaphore(max(1, args.rate))
    start = time.perf_counter()
    async def task(i):
        async with sem:
            # Pace requests approximately at offered rate.
            if args.rate > 0:
                await asyncio.sleep(i / args.rate)
            q = QUESTIONS[i % len(QUESTIONS)]
            await run_one(q, args.backend, args.scenario)
    await asyncio.gather(*(task(i) for i in range(args.requests)))
    print(f"Completed {args.requests} requests in {time.perf_counter()-start:.2f}s")

def main():
    parser = argparse.ArgumentParser(description="The Relay research assistant")
    sub = parser.add_subparsers(dest="command", required=True)
    ask = sub.add_parser("ask")
    ask.add_argument("question")
    ask.add_argument("--backend", choices=["groq","standin"], default=None)
    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--backend", choices=["groq","standin"], default="standin")
    load = sub.add_parser("load")
    load.add_argument("--backend", choices=["groq","standin"], default="standin")
    load.add_argument("--scenario", choices=["steady","burst","overload","minute_halved","daily_exhausted"], default="steady")
    load.add_argument("--requests", type=int, default=20)
    load.add_argument("--rate", type=float, default=4)
    sub.add_parser("report")
    args = parser.parse_args()

    if args.command == "ask":
        asyncio.run(run_one(args.question, args.backend, "single"))
    elif args.command == "evaluate":
        for q in QUESTIONS:
            asyncio.run(run_one(q, args.backend, "evaluation"))
    elif args.command == "load":
        if args.scenario == "daily_exhausted":
            print("NOTE: This is a local stand-in budget simulation only; it does not exhaust Groq's daily quota.")
        if args.scenario == "minute_halved":
            print("NOTE: Configure stand-in rate limit/failure settings to model a reduced quota; this starter does not change Groq account limits.")
        asyncio.run(load_run(args))
    elif args.command == "report":
        generate_report_tables()

if __name__ == "__main__":
    main()
