#!/usr/bin/env python3
"""Fair benchmark: max_tokens=4096 for reasoning models, actual BILUN context."""

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

API_KEY = (os.environ.get("LLM_API_KEY", "").strip() or os.environ.get("OPENROUTER_API_KEY", "").strip())
ENDPOINT = os.getenv("LLM_ENDPOINT", "https://openrouter.ai/api/v1/chat/completions")
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json", "HTTP-Referer": "https://bilun.app"}

# Light context — cohort-level question
from src.bilun.chatbot.prompts import build_system_prompt
from src.bilun.chatbot.metadata import get_chat_model_context
from src.bilun.api.routes.chat import _fetch_runtime_data
from src.bilun.chatbot.context import build_bilun_runtime_context

raw = _fetch_runtime_data("SUT Analytics", None, user_message=None, intent="user_question")
runtime_ctx = build_bilun_runtime_context(raw, "SUT Analytics", None, intent="user_question")
sys_prompt = build_system_prompt(get_chat_model_context(), intent="user_question")
full_context = sys_prompt + "\n\n" + runtime_ctx

QUESTION = "What does the cohort optimization tell us about copay exemptions? Give a one-sentence answer."

print(f"Context size: {len(full_context)} chars")
print(f"Question: {QUESTION}")
print()

MODELS = [
    ("deepseek/deepseek-v4-pro",     "DeepSeek V4 Pro     "),
    ("deepseek/deepseek-chat",       "DeepSeek V3          "),
    ("qwen/qwen-plus",               "Qwen Plus            "),
    ("moonshotai/kimi-k2.6",         "Moonshot Kimi K2.6   "),
    ("stepfun/step-3.7-flash",       "StepFun Step 3.7 Flash"),
    ("xiaomi/mimo-v2.5-pro",         "Xiaomi MiMo v2.5 Pro "),
    ("qwen/qwen3.7-max",             "Qwen 3.7 Max         "),
]


async def bench(model_id: str, label: str) -> dict:
    print(f"{label}: {model_id}")
    payload = {
        "model": model_id, "messages": [
            {"role": "system", "content": full_context},
            {"role": "user", "content": QUESTION},
        ],
        "max_tokens": 4096, "temperature": 0.4, "stream": True,
    }

    t0 = time.perf_counter()
    ttft = None
    content_tokens = 0
    reasoning_tokens = 0
    content_text: list[str] = []

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            async with client.stream("POST", ENDPOINT, headers=HEADERS, json=payload) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    return {"label": label, "error": f"HTTP {resp.status_code}: {body[:200].decode()}"}
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "): continue
                    raw = line[6:]
                    if raw.strip() == "[DONE]": break
                    try:
                        chunk = json.loads(raw)
                        delta = chunk["choices"][0]["delta"]
                        c = delta.get("content")
                        r = delta.get("reasoning") or delta.get("reasoning_content")
                        if r:
                            reasoning_tokens += 1
                        if c:
                            if ttft is None:
                                ttft = time.perf_counter() - t0
                            content_tokens += 1
                            content_text.append(c)
                    except (json.JSONDecodeError, KeyError, IndexError):
                        pass
    except Exception as exc:
        return {"label": label, "error": f"{type(exc).__name__}: {exc}"}

    elapsed = time.perf_counter() - t0
    return {
        "label": label, "ttft": round(ttft, 2) if ttft else None,
        "total": round(elapsed, 2), "content_tok": content_tokens,
        "reasoning_tok": reasoning_tokens,
        "preview": "".join(content_text).strip()[:120],
    }


async def main() -> None:
    results = []
    for mid, label in MODELS:
        r = await bench(mid, label)
        results.append(r)
        if "error" in r:
            print(f"  ❌ {r['error']}")
        else:
            print(f"  ✓ ttft={r['ttft']}s total={r['total']}s content={r['content_tok']}t reason={r['reasoning_tok']}t")
            if r["preview"]:
                print(f"    {r['preview'][:100]}")
        print()
        await asyncio.sleep(1.0)

    print(f"\n{'='*95}")
    header = f"  {'Model':<27} {'TTFT':>8} {'Total':>8} {'Tok':>6} {'Reason':>7} {'T/s':>7}"
    print(header)
    print("  " + "-" * 90)
    for r in results:
        if "error" in r:
            print(f"  {r['label']:<27} ❌ {r['error'][:55]}")
        else:
            ttft = f"{r['ttft']:.2f}s" if r['ttft'] else "N/A"
            tps = f"{r['content_tok']/r['total']:.1f}" if r['total'] > 0 else "0"
            print(f"  {r['label']:<27} {ttft:>8} {r['total']:>7.2f}s {r['content_tok']:>6d} {r['reasoning_tok']:>7d} {tps:>7}")

    # Winner
    winners = [r for r in results if "ttft" in r and r["ttft"] is not None and r["content_tok"] > 0]
    if winners:
        best = min(winners, key=lambda r: r["ttft"])
        print(f"\n  → Winner (lowest TTFT with content): {best['label'].strip()} ({best['ttft']}s)")


if __name__ == "__main__":
    asyncio.run(main())
