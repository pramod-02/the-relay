import asyncio
import os
import random
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse

app = FastAPI(title="The Relay Stand-in Model Service")
semaphore = asyncio.Semaphore(int(os.getenv("STANDIN_MAX_IN_FLIGHT", "4")))
counter_lock = asyncio.Lock()
active = 0
request_count = 0

@app.get("/health")
async def health():
    return {"status": "ok", "active": active, "requests": request_count}

@app.post("/generate")
async def generate(request: Request):
    global active, request_count
    body = await request.json()
    prompt = str(body.get("prompt", ""))
    async with counter_lock:
        request_count += 1
        this_request = request_count

    # Deterministic fault injection knobs via environment variables.
    fail_every = int(os.getenv("STANDIN_FAIL_EVERY", "0"))
    rate_every = int(os.getenv("STANDIN_RATE_LIMIT_EVERY", "0"))
    slow_ms = int(os.getenv("STANDIN_BASE_DELAY_MS", "350"))
    per_active_ms = int(os.getenv("STANDIN_PER_ACTIVE_MS", "180"))
    if fail_every and this_request % fail_every == 0:
        return JSONResponse({"error": "injected failure"}, status_code=503)
    if rate_every and this_request % rate_every == 0:
        return JSONResponse({"error": "injected rate limit"}, status_code=429, headers={"Retry-After": "1"})

    async def stream():
        global active
        acquired = False
        try:
            await semaphore.acquire()
            acquired = True
            active += 1
            delay = (slow_ms + active * per_active_ms + random.randint(0, 100)) / 1000
            await asyncio.sleep(delay)
            # Stand-in intentionally does not perform reasoning; it is a transport/load simulator.
            if "what is" in prompt.lower() or "explain" in prompt.lower():
                answer = "DEMO STAND-IN: This service simulates latency and streaming only. Replace this response with a real Groq answer for quality evaluation."
            else:
                answer = "DEMO STAND-IN: No model reasoning is performed by the simulator."
            for word in answer.split():
                yield f"data: {word}\n\n"
                await asyncio.sleep(0.025)
            yield "data: [DONE]\n\n"
        finally:
            if acquired:
                active -= 1
                semaphore.release()

    return StreamingResponse(stream(), media_type="text/event-stream")
