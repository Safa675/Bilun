#!/usr/bin/env python3
"""Deep-dive: check raw message keys for models returning empty content."""

from __future__ import annotations

import asyncio
import json
import os
import sys
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

MESSAGES = [{"role": "user", "content": "Say 'hello' in Turkish and stop."}]


async def deep_check(model_id: str, label: str) -> None:
    print(f"\n{'='*70}")
    print(f"  {label}: {model_id}")
    print(f"{'='*70}")

    # Non-streaming with LARGE max_tokens to give thinking models room
    for max_tok in [256]:
        payload = {
            "model": model_id, "messages": MESSAGES,
            "max_tokens": max_tok, "temperature": 0.0, "stream": False,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(ENDPOINT, headers=HEADERS, json=payload)
            body = resp.text

        print(f"  max_tokens={max_tok} | HTTP {resp.status_code}")
        try:
            data = json.loads(body)
            choice = data["choices"][0]
            finish = choice.get("finish_reason", "?")
            msg = choice.get("message", {})
            print(f"  finish_reason: {finish}")
            print(f"  message keys: {list(msg.keys())}")
            for key, val in msg.items():
                s = str(val)
                print(f"    {key}: {s[:200]}{'...' if len(s) > 200 else ''}")
        except Exception as e:
            print(f"  Parse error: {e}")
            print(f"  Raw body (first 500 chars): {body[:500]}")

    # Also test with OpenRouter's "include_reasoning" parameter set to true
    payload2 = {
        "model": model_id, "messages": MESSAGES,
        "max_tokens": 256, "temperature": 0.0, "stream": False,
        "include_reasoning": True,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(ENDPOINT, headers=HEADERS, json=payload2)
        body = resp.text
    print(f"\n  With include_reasoning=true | HTTP {resp.status_code}")
    try:
        data = json.loads(body)
        choice = data["choices"][0]
        finish = choice.get("finish_reason", "?")
        msg = choice.get("message", {})
        print(f"  finish_reason: {finish}")
        print(f"  message keys: {list(msg.keys())}")
        for key, val in msg.items():
            s = str(val)
            print(f"    {key}: {s[:200]}{'...' if len(s) > 200 else ''}")
    except Exception as e:
        print(f"  Parse error: {e}")
        print(f"  Raw body (first 500 chars): {body[:500]}")


async def main() -> None:
    suspects = [
        ("deepseek/deepseek-v4-pro", "DeepSeek V4 Pro"),
        ("moonshotai/kimi-k2.6",     "Moonshot Kimi K2.6"),
        ("stepfun/step-3.7-flash",   "StepFun Step 3.7 Flash"),
    ]
    for mid, label in suspects:
        await deep_check(mid, label)
        await asyncio.sleep(0.5)

if __name__ == "__main__":
    asyncio.run(main())
