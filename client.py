"""promptmap LLM backend: DeepSeek V4.1 Flash via OpenRouter (key: OPENROUTER_API_KEY in .env).

Also registers one project model kind:
  local_dir   config(path="seed")  -> promptmap.Dir of a repo folder (input tree for agents)
"""
import os
import sys
import time
from pathlib import Path

from openai import OpenAI

import promptmap
ROOT = Path(__file__).parent


@promptmap.model_kind("local_dir", config_keys={"path"})
async def local_dir(rendered, call):
    return promptmap.Dir(ROOT / call.spec.config["path"], name=call.spec.name)


MODEL = "deepseek/deepseek-v4.1-flash"  # was moonshotai/kimi-k3.1-pro (out of credits, 40x pricier)
# Agent kinds run mini-swe-agent (promptmap >= 0.7), which names models the litellm way.
agent_model = f"openrouter/{MODEL}"

# litellm has no price for v4.1-flash, and mini-swe-agent stops on an unknown cost.
# Register OpenRouter's price (per token) so agent_cost_limit keeps working.
try:
    import litellm

    litellm.register_model({agent_model: {
        "input_cost_per_token": 0.045e-6, "output_cost_per_token": 0.5e-6,
        "litellm_provider": "openrouter", "mode": "chat", "max_input_tokens": 1048576,
    }})
except ImportError:  # litellm only matters for agent kinds
    pass


def llm_call(prompt: str, files: list | None = None, config: dict | None = None) -> promptmap.LLMResult:
    # Streamed: Kimi reasons silently for minutes; a non-streamed call sits idle
    # and a proxy in the path held it open forever (spec hung 50 min). Streaming
    # keeps bytes flowing; the timeout makes any remaining hang fail loudly.
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
        timeout=180.0,  # max silence between chunks, not total duration
        max_retries=1,
    )
    kwargs = {}
    if (config or {}).get("output_format") == "json":
        kwargs["response_format"] = {"type": "json_object"}
    stream = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        stream=True,
        stream_options={"include_usage": True},
        # Uncapped, Kimi reasoned 70+ min on spec without writing a word
        # (heartbeat: reasoning=21k chars, content=0 at 3 min). Cap it.
        extra_body={"reasoning": {"effort": (config or {}).get("reasoning_effort", "low")}},
        **kwargs,
    )
    parts, tokens = [], None
    reasoning_chars, started, last_log = 0, time.monotonic(), time.monotonic()
    for chunk in stream:
        if chunk.choices:
            delta = chunk.choices[0].delta
            if delta.content:
                parts.append(delta.content)
            reasoning_chars += len(getattr(delta, "reasoning", None) or (delta.model_extra or {}).get("reasoning") or "")
        if chunk.usage:
            tokens = chunk.usage.total_tokens
        if time.monotonic() - last_log > 60:  # heartbeat: shows whether it's thinking or writing
            last_log = time.monotonic()
            print(f"[llm] {int(last_log - started)}s reasoning={reasoning_chars} content={sum(map(len, parts))}",
                  file=sys.stderr, flush=True)
    return promptmap.LLMResult("".join(parts), spent_tokens=tokens)
