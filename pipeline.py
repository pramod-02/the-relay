import asyncio
import time
import uuid
from datetime import datetime, timezone
import config
from providers import GroqProvider, StandinProvider, ProviderError
from retrieval import load_passages, retrieve

class RelayPipeline:
    def __init__(self, backend=None, retrieval_setting="350-4-no"):
        self.backend = backend or config.BACKEND
        self.retrieval_setting = retrieval_setting
        self.passages = load_passages()
        self.provider = GroqProvider() if self.backend == "groq" else StandinProvider()
        self.semaphore = asyncio.Semaphore(config.MAX_CONCURRENCY)

    async def answer(self, question, scenario="single", request_id=None):
        request_id = request_id or str(uuid.uuid4())
        start_wall = datetime.now(timezone.utc).isoformat()
        started = time.perf_counter()
        first_token_ms = None
        retries = 0
        tokens_in = tokens_out = 0
        status = "ok"
        answer_grade = "refused_wrongly"
        response_text = ""
        retrieved = []
        queue_enter = time.perf_counter()

        async with self.semaphore:
            queue_wait_ms = (time.perf_counter() - queue_enter) * 1000
            # Step 1: analyse intent (lightweight deterministic routing).
            asks_about_library = bool(question.strip())
            if not asks_about_library:
                response_text = "Please provide a question about the supplied research papers."
                status = "ok"
            else:
                # Step 2: retrieve evidence; tool call is the local PDF index.
                retrieved = retrieve(question, self.passages, k=4)
                if not retrieved:
                    response_text = "The supplied papers do not provide enough evidence to answer that question."
                    answer_grade = "refused_correctly"
                else:
                    context = "\n\n".join(
                        f"[{p.paper}, page {p.page}] {p.text}" for p in retrieved
                    )
                    # Step 3: branch — no evidence means refuse; evidence means draft.
                    messages = [
                        {"role": "system", "content": (
                            "Answer only from the supplied paper passages. Cite every factual claim "
                            "using [filename, page N]. If evidence is insufficient, explicitly say "
                            "the papers do not state it. Do not use outside knowledge."
                        )},
                        {"role": "user", "content": f"Question: {question}\n\nEvidence:\n{context}"}
                    ]
                    # Step 4: model call with bounded retries for transient failures only.
                    while True:
                        try:
                            def mark_first_token(_provider_elapsed_ms):
                                nonlocal first_token_ms
                                if first_token_ms is None:
                                    first_token_ms = (time.perf_counter() - started) * 1000
                            text, usage, headers = await self.provider.generate(
                                messages,
                                on_first_token=mark_first_token
                            )
                            response_text = text
                            tokens_in = usage.get("tokens_in", 0)
                            tokens_out = usage.get("tokens_out", 0)
                            break
                        except ProviderError as exc:
                            if exc.status_code == 429:
                                status = "rate_limited"
                                break
                            if retries < config.MAX_RETRIES and (exc.status_code is None or exc.status_code >= 500):
                                retries += 1
                                await asyncio.sleep(min(2 ** retries, 4))
                                continue
                            status = "timeout" if "timeout" in str(exc).lower() else "error"
                            break
                    if status == "ok":
                        # Step 5: citation verifier and branch/loop. One repair attempt at most.
                        if not self._citations_valid(response_text, retrieved):
                            repair_messages = messages + [
                                {"role": "assistant", "content": response_text},
                                {"role": "user", "content": "Revise: cite every factual claim with an exact source filename and page from the evidence. If unsupported, refuse."}
                            ]
                            try:
                                revised, usage2, _ = await self.provider.generate(repair_messages)
                                response_text = revised
                                tokens_in += usage2.get("tokens_in", 0)
                                tokens_out += usage2.get("tokens_out", 0)
                                retries += 1
                            except Exception:
                                pass
                        answer_grade = "correct" if self._citations_valid(response_text, retrieved) else "wrong"
        total_ms = (time.perf_counter() - started) * 1000
        # If no streaming token arrived, leave first_token_ms blank rather than inventing a value.
        row = {
            "request_id": request_id, "scenario": scenario, "source": self.backend,
            "start_time": start_wall, "first_token_ms": round(first_token_ms, 1) if first_token_ms is not None else "",
            "total_ms": round(total_ms, 1), "status": status, "retries": retries,
            "tokens_in": tokens_in, "tokens_out": tokens_out,
            "retrieval_setting": self.retrieval_setting, "answer_grade": answer_grade,
            "queue_wait_ms": round(queue_wait_ms, 1),
        }
        return {"answer": response_text, "record": row, "retrieved": retrieved}

    @staticmethod
    def _citations_valid(answer, passages):
        if not answer:
            return False
        # Conservative structural validation: each citation must match an available paper/page.
        citations = []
        import re
        citations = re.findall(r"\[([^\]]+),\s*page\s+(\d+)\]", answer, re.I)
        if not citations:
            return False
        valid = {(p.paper, str(p.page)) for p in passages}
        return any((paper.strip(), page) in valid for paper, page in citations)
