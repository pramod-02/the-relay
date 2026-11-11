import asyncio
import time
import httpx
from groq import AsyncGroq
from . import config

class ProviderError(Exception):
    def __init__(self, message, status_code=None, retry_after=None, headers=None):
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after
        self.headers = headers or {}

class GroqProvider:
    def __init__(self):
        if not config.GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is missing. Add it as a Codespaces secret or in .env.")
        self.client = AsyncGroq(api_key=config.GROQ_API_KEY, timeout=config.REQUEST_TIMEOUT_SECONDS)

    async def generate(self, messages, on_first_token=None):
        started = time.perf_counter()
        chunks = []
        usage = {"tokens_in": 0, "tokens_out": 0}
        try:
            stream = await self.client.chat.completions.create(
                model=config.GROQ_MODEL,
                messages=messages,
                temperature=0,
                max_tokens=500,
                stream=True,
                stream_options={"include_usage": True},
            )
            async for chunk in stream:
                if chunk.choices:
                    content = chunk.choices[0].delta.content
                    if content:
                        if on_first_token and not chunks:
                            on_first_token((time.perf_counter() - started) * 1000)
                        chunks.append(content)
                if getattr(chunk, "usage", None):
                    usage["tokens_in"] = chunk.usage.prompt_tokens or 0
                    usage["tokens_out"] = chunk.usage.completion_tokens or 0
            return "".join(chunks), usage, {}
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            headers = getattr(exc, "response", None)
            hdrs = dict(headers.headers) if headers is not None and getattr(headers, "headers", None) else {}
            retry_after = hdrs.get("retry-after")
            raise ProviderError(str(exc), status, retry_after, hdrs) from exc

class StandinProvider:
    def __init__(self, base_url=None):
        self.base_url = base_url or config.STANDIN_URL

    async def generate(self, messages, on_first_token=None):
        prompt = "\n".join(str(m.get("content", "")) for m in messages)
        async with httpx.AsyncClient(timeout=config.REQUEST_TIMEOUT_SECONDS) as client:
            try:
                async with client.stream("POST", self.base_url + "/generate", json={"prompt": prompt}) as response:
                    if response.status_code == 429:
                        raise ProviderError("Stand-in rate limited", 429, response.headers.get("retry-after"), dict(response.headers))
                    response.raise_for_status()
                    pieces = []
                    first = True
                    async for line in response.aiter_lines():
                        if line.startswith("data:"):
                            piece = line[5:].strip()
                            if piece == "[DONE]":
                                break
                            if piece:
                                if first and on_first_token:
                                    on_first_token(0)  # Pipeline measures end-to-end first-token time.
                                first = False
                                pieces.append(piece)
                    answer = " ".join(pieces)
                    return answer, {"tokens_in": max(1, len(prompt.split())), "tokens_out": max(1, len(answer.split()))}, dict(response.headers)
            except ProviderError:
                raise
            except httpx.TimeoutException as exc:
                raise ProviderError("Stand-in timeout") from exc
            except httpx.HTTPStatusError as exc:
                raise ProviderError(str(exc), exc.response.status_code, exc.response.headers.get("retry-after"), dict(exc.response.headers)) from exc
