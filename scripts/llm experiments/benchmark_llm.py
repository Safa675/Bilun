#!/usr/bin/env python3
"""Benchmark open-weight LLM models vs current v4-pro for BILUN chat response time.

Measures TTFT (time to first token), total time, token count, and tokens/sec
using the same prompt + context BILUN chat normally sends.

Usage:
    .venv/bin/python scripts/benchmark_llm.py
"""

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

# ── Open-weight models to benchmark ──────────────────────────────────────────
# Current baseline first, then genuinely open-weight alternatives.
# ":free" suffix = OpenRouter hosted for free (community sponsored).
MODELS: list[tuple[str, str]] = [
    ("deepseek/deepseek-v4-pro",     "DeepSeek V4 Pro (current)"),
    ("deepseek/deepseek-chat",       "DeepSeek V3 (open weight)"),
    ("qwen/qwen-plus",               "Qwen Plus (open weight)"),
    ("qwen/qwen3.7-max",             "Qwen 3.7 Max"),
    ("moonshotai/kimi-k2.6",         "Moonshot Kimi K2.6"),
    ("xiaomi/mimo-v2.5-pro",         "Xiaomi MiMo v2.5 Pro"),
    ("stepfun/step-3.7-flash",       "StepFun Step 3.7 Flash"),
]

# ── Build representative context (same path as BILUN chat) ───────────────────

def _build_context() -> str:
    import duckdb
    from src.bilun.chatbot.context import build_bilun_runtime_context
    from src.bilun.api.routes.chat import _fetch_runtime_data

    raw = _fetch_runtime_data(
        "SUT Analytics",
        None,  # cohort/home view — no patient
        user_message=None,
        intent="user_question",
    )

    ctx = build_bilun_runtime_context(
        raw, "SUT Analytics", None, page_context=None, intent="user_question"
    )
    return ctx


def _build_sys_prompt() -> str:
    from src.bilun.chatbot.prompts import build_system_prompt
    from src.bilun.chatbot.metadata import get_chat_model_context
    return build_system_prompt(get_chat_model_context(), intent="user_question")


SYS_PROMPT = _build_sys_prompt()
RUNTIME_CTX = _build_context()

# Short representative question — keep it small so we test model speed, not
# prompt-engineering skill. Same question across all models.
USER_QUESTION = (
    "What is the total recoverable TRY across all patients, "
    "and which billing category contributes the most? Answer in one paragraph."
)

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://bilun.app",
    "X-Title": "BILUN Benchmark",
}

# ── Benchmark loop ───────────────────────────────────────────────────────────

async def benchmark_one(
    model_id: str,
    label: str,
    num_runs: int = 1,
) -> list[dict[str, Any]]:
    print(f"\n{'='*72}")
    print(f"  {label}")
    print(f"  Model: {model_id}")
    print(f"{'='*72}")

    results: list[dict[str, Any]] = []

    for run_i in range(num_runs):
        if num_runs > 1:
            print(f"  --- Run {run_i + 1}/{num_runs} ---")

        payload: dict[str, Any] = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": SYS_PROMPT + "\n\n" + RUNTIME_CTX},
                {"role": "user", "content": USER_QUESTION},
            ],
            "max_tokens": 512,
            "temperature": 0.4,
            "stream": True,
        }

        t0 = time.perf_counter()
        ttft: float | None = None
        token_count = 0
        full_text: list[str] = []

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST", ENDPOINT, headers=HEADERS, json=payload
                ) as response:
                    if response.status_code != 200:
                        body = await response.aread()
                        print(f"  ❌ HTTP {response.status_code}: {body[:300].decode()}")
                        results.append({
                            "model": model_id,
                            "label": label,
                            "error": f"HTTP {response.status_code}",
                        })
                        continue

                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data = line[6:]
                        if data.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            delta = chunk["choices"][0]["delta"]
                            token = delta.get("content") or delta.get("reasoning_content")
                            if token:
                                if ttft is None:
                                    ttft = time.perf_counter() - t0
                                token_count += 1
                                full_text.append(token)
                        except (json.JSONDecodeError, KeyError, IndexError):
                            pass
        except asyncio.TimeoutError:
            print(f"  ❌ Timeout after 120s")
            results.append({
                "model": model_id,
                "label": label,
                "error": "timeout",
            })
            continue
        except Exception as exc:
            print(f"  ❌ Error: {exc}")
            results.append({
                "model": model_id,
                "label": label,
                "error": f"{type(exc).__name__}: {exc}",
            })
            continue

        elapsed = time.perf_counter() - t0
        tps = token_count / elapsed if elapsed > 0 else 0.0
        response_text = "".join(full_text)

        results.append({
            "model": model_id,
            "label": label,
            "ttft_sec": round(ttft, 3) if ttft else None,
            "total_sec": round(elapsed, 2),
            "tokens": token_count,
            "tokens_per_sec": round(tps, 1),
            "response": response_text[:200] + "..." if len(response_text) > 200 else response_text,
        })

        print(f"    TTFT:      {ttft:.3f}s" if ttft else "    TTFT:      N/A")
        print(f"    Total:     {elapsed:.2f}s")
        print(f"    Tokens:    {token_count}")
        print(f"    Tokens/s:  {tps:.1f}")
        print(f"    Preview:   {response_text[:150].strip()}...")

        if num_runs > 1:
            await asyncio.sleep(1.0)

    return results


async def main() -> None:
    if not API_KEY:
        print("❌ No API key found. Set OPENROUTER_API_KEY or LLM_API_KEY in .env")
        sys.exit(1)

    print("=" * 72)
    print("  BILUN Chatbot LLM Benchmark — Open Weight Models")
    print("=" * 72)
    print(f"  Endpoint:  {ENDPOINT}")
    print(f"  Prompt chars: {len(SYS_PROMPT + RUNTIME_CTX + USER_QUESTION)}")
    print(f"  Question:  {USER_QUESTION}")
    print()
    print("  Measuring: TTFT (time-to-first-token), total time, tokens/sec")
    print("  Lower TTFT = more responsive chatbot feel.")
    print()

    all_results: list[dict[str, Any]] = []

    for model_id, label in MODELS:
        results = await benchmark_one(model_id, label, num_runs=1)
        all_results.extend(results)
        await asyncio.sleep(1.0)

    # ── Summary table ────────────────────────────────────────────────────────
    print()
    print("=" * 90)
    print("  SUMMARY")
    print("=" * 90)
    header = f"  {'Model':<38} {'TTFT (s)':>10} {'Total (s)':>10} {'Tok/s':>8} {'Tokens':>7}"
    print(header)
    print("  " + "-" * 85)

    best_ttft = float("inf")
    best_model = ""

    for r in all_results:
        if "error" in r:
            line = f"  {r['label']:<38} {'FAILED':>10}  ({r['error']})"
        else:
            ttft_str = f"{r['ttft_sec']:.3f}" if r['ttft_sec'] is not None else "N/A"
            line = (
                f"  {r['label']:<38} "
                f"{ttft_str:>10s} "
                f"{r['total_sec']:>10.2f} "
                f"{r['tokens_per_sec']:>8.1f} "
                f"{r['tokens']:>7d}"
            )
            if r["ttft_sec"] is not None and r["ttft_sec"] < best_ttft:
                best_ttft = r["ttft_sec"]
                best_model = r["label"]
        print(line)

    if best_model:
        print(f"\n  → Fastest TTFT: {best_model} ({best_ttft:.3f}s)")


if __name__ == "__main__":
    asyncio.run(main())
