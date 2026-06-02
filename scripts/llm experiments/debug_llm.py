#!/usr/bin/env python3
"""Debug benchmark: log raw HTTP responses, test both streaming + non-streaming."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from dotenv import load_dotenv
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

API_KEY = (
    os.environ.get("LLM_API_KEY", "").strip()
    or os.environ.get("OPENROUTER_API_KEY", "").strip()
)
ENDPOINT = os.getenv("LLM_ENDPOINT", "https://openrouter.ai/api/v1/chat/completions")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://bilun.app",
    "X-Title": "BILUN Bench",
}

# Short, simple prompt to rule out context-size issues
MESSAGES = [
    {"role": "user", "content": "Say 'hello' in Turkish and stop."},
]


async def test_model(model_id: str, label: str) -> dict[str, Any]:
    result: dict[str, Any] = {"model": model_id, "label": label}

    # ── Non-streaming first (most reliable) ──────────────────────────────
    payload_ns = {
        "model": model_id,
        "messages": MESSAGES,
        "max_tokens": 32,
        "temperature": 0.0,
        "stream": False,
    }

    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(ENDPOINT, headers=HEADERS, json=payload_ns)
            body = resp.text
            status = resp.status_code
    except Exception as exc:
        result["ns_error"] = f"{type(exc).__name__}: {exc}"
        response_text = result.get("ns_error", "?")
        return result

    t_ns = time.perf_counter() - t0

    if status != 200:
        result["ns_error"] = f"HTTP {status}: {body[:300]}"
        return result

    try:
        data = json.loads(body)
        msg = data["choices"][0]["message"]
        content = (msg.get("content") or "").strip()
        reasoning = (msg.get("reasoning_content") or "").strip()
        finish = data["choices"][0].get("finish_reason", "?")
        result["ns_content"] = content or reasoning or ""
        result["ns_finish"] = finish
        result["ns_time"] = round(t_ns, 2)
        result["ns_raw_keys"] = list(msg.keys())
    except (json.JSONDecodeError, KeyError) as exc:
        result["ns_error"] = f"Parse: {exc} | body={body[:300]}"
        return result

    # ── Streaming test ───────────────────────────────────────────────────
    payload_s = {
        "model": model_id,
        "messages": MESSAGES,
        "max_tokens": 32,
        "temperature": 0.0,
        "stream": True,
    }

    t0 = time.perf_counter()
    ttft: float | None = None
    tokens: list[str] = []
    sse_lines: list[str] = []

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", ENDPOINT, headers=HEADERS, json=payload_s) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    result["s_error"] = f"HTTP {resp.status_code}: {body[:300].decode()}"
                    return result

                async for line in resp.aiter_lines():
                    sse_lines.append(line[:120])
                    if not line.startswith("data: "):
                        continue
                    raw = line[6:]
                    if raw.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(raw)
                        delta = chunk["choices"][0]["delta"]
                        token = delta.get("content") or delta.get("reasoning_content")
                        if token:
                            if ttft is None:
                                ttft = time.perf_counter() - t0
                            tokens.append(token)
                    except (json.JSONDecodeError, KeyError, IndexError):
                        pass
    except Exception as exc:
        result["s_error"] = f"{type(exc).__name__}: {exc}"
        return result

    t_s = time.perf_counter() - t0
    result["s_ttft"] = round(ttft, 3) if ttft else None
    result["s_content"] = "".join(tokens).strip()
    result["s_tokens"] = len(tokens)
    result["s_time"] = round(t_s, 2)
    result["s_first_lines"] = sse_lines[:8]

    return result


async def main() -> None:
    print(f"{'='*80}")
    print(f"  BILUN LLM Debug — non-streaming + streaming, 4-token prompt")
    print(f"{'='*80}")
    print()

    MODELS = [
        ("deepseek/deepseek-v4-pro",  "DeepSeek V4 Pro"),
        ("deepseek/deepseek-chat",    "DeepSeek V3"),
        ("qwen/qwen-plus",            "Qwen Plus"),
        ("moonshotai/kimi-k2.6",      "Moonshot Kimi K2.6"),
        ("stepfun/step-3.7-flash",    "StepFun Step 3.7 Flash"),
    ]

    results: list[dict] = []

    for model_id, label in MODELS:
        print(f"--- {label}: {model_id} ---")
        r = await test_model(model_id, label)
        results.append(r)

        if "ns_error" in r:
            print(f"  NON-STREAMING: ❌ {r['ns_error']}")
        else:
            print(f"  NON-STREAMING: {r['ns_time']:.2f}s | finish={r.get('ns_finish')} | content={r.get('ns_content', '')[:80]!r}")

        if "s_error" in r:
            print(f"  STREAMING:     ❌ {r['s_error']}")
        else:
            ttft = f"{r['s_ttft']:.3f}s" if r['s_ttft'] else "N/A"
            print(f"  STREAMING:     ttft={ttft} total={r['s_time']:.2f}s | tokens={r['s_tokens']} | content={r.get('s_content', '')[:80]!r}")
            if r.get("s_first_lines"):
                print(f"    First SSE lines: {r['s_first_lines']}")

        print()
        await asyncio.sleep(0.5)

    print(f"{'='*80}")
    print(f"  SUMMARY")
    print(f"{'='*80}")
    for r in results:
        ns_ok = "ns_error" not in r
        s_ok = "s_error" not in r
        ns_str = f"{r.get('ns_content', '') or r.get('ns_error', '')[:60]!r}" if ns_ok else f"❌ {r.get('ns_error')[:40]!r}"
        s_str = f"ttft={r.get('s_ttft')} tok={r.get('s_tokens')}" if s_ok else f"❌ {r.get('s_error')[:40]!r}"
        print(f"  {r['label']:<25} ns={ns_str:<50} s={s_str}")


if __name__ == "__main__":
    asyncio.run(main())
