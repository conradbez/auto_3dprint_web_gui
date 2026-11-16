"""promptmap LLM backend: OpenRouter, models from settings.yml (key: OPENROUTER_API_KEY in .env).
Aliases: low = DeepSeek V4.1 Flash (default), medium = Kimi K3.1 Pro.

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


# Models come from settings.yml: `model` is the default, `aliases` (low, medium)
# are picked per model with {{ config(model="medium") }}.
from promptmap.settings import load_settings, model_aliases, resolve_model

_SETTINGS = load_settings(str(ROOT / "map"))
_ALIASES = model_aliases(_SETTINGS)


def _openrouter_model(name: str | None) -> str:
    """config(model=...) (an alias or provider/model) -> OpenRouter model id."""
    provider, model = resolve_model(_SETTINGS, model=name)
    if provider != "openrouter":
        raise ValueError(f"client.py only calls OpenRouter; {name or 'default'} resolved to {provider}/{model}")
    return model


# Agent kinds run mini-swe-agent (promptmap >= 0.7), which names models the litellm way.
agent_model = "openrouter/" + _openrouter_model(None)

# litellm has no price for these, and mini-swe-agent stops on an unknown cost.
# Register OpenRouter's price (per token, 2026-11-16) so agent_cost_limit keeps working.
_PRICES = {
    "deepseek/deepseek-v4.1-flash": (0.14e-6, 0.42e-6),
    "moonshotai/kimi-k3.1-pro": (0.2403e-6, 8.4023e-6),
}
try:
    import litellm

    litellm.register_model({f"openrouter/{m}": {
        "input_cost_per_token": i, "output_cost_per_token": o,
        "litellm_provider": "openrouter", "mode": "chat", "max_input_tokens": 1048576,
    } for m, (i, o) in _PRICES.items()})
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
        model=_openrouter_model((config or {}).get("model")),
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
