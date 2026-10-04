"""Any OpenAI-compatible chat endpoint: Zhipu, Qwen, DeepSeek, Kimi, OpenRouter, OpenAI, Google's
compatible layer, MiniMax, a local Ollama, or a custom one (the providers of ThoughtDAG).

Not every provider honours a JSON schema, so the schema rides in the prompt and JSON mode is asked for;
a provider that rejects JSON mode is asked again without it.

A reasoning level (spec["effort"]: off, low, medium, high; None for the model's own) is spelled the way each provider
documents it. These spellings change as APIs change, so none of them is relied on: a request a provider refuses is
sent again the next way, and last with no reasoning field at all, which every endpoint takes. The way that worked is
remembered for the rest of the run.
"""
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

_WORKED = {}   # (base, model, level) -> index of the request shape that was accepted
WAITS = (5, 15, 30, 45)   # seconds before asking again when rate-limited (free models: 20 requests a minute)


def _post(url, body, headers, timeout):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def reasoning(base, level):
    """The fields that ask a provider for a level of reasoning, most fitting first: the provider's own spelling, then
    OpenAI's reasoning_effort (which many take), for off down to the least a model allows (some always think), and
    last {} (the model's default), which every endpoint takes."""
    host = urllib.parse.urlparse(base).netloc
    if level is None:
        return ([{"reasoning": {"enabled": True}}] if "openrouter.ai" in host else []) + [{}]
    on = level != "off"
    generic = [{"reasoning_effort": level}] if on else [{"reasoning_effort": x} for x in ("none", "minimal", "low")]
    toggle = {"thinking": {"type": "enabled" if on else "disabled"}}
    if "openrouter.ai" in host:
        own = [{"reasoning": {"effort": level}}] if on else [{"reasoning": {"enabled": False}}, {"reasoning": {"effort": "low"}}]
    elif any(h in host for h in ("bigmodel.cn", "z.ai")):   # GLM: a level by reasoning_effort, off by the toggle (where it exists)
        own, generic = ([], generic + [toggle]) if on else ([toggle], generic)
    elif any(h in host for h in ("deepseek.com", "moonshot.", "kimi.com")):
        own = [toggle]
    elif "dashscope" in host:   # Qwen
        own = [{"enable_thinking": on, **({"thinking_budget": {"low": 2048, "medium": 8192}[level]} if level in ("low", "medium") else {})}]
    elif "minimax" in host:     # always thinks; nothing to set
        own, generic = [], []
    else:
        own = []
    return own + generic + [{}]


def call(prompt, schema, spec, system, timeout):
    base = (spec.get("base") or "https://api.openai.com/v1").rstrip("/")
    level = spec.get("effort")
    body = {
        "model": spec["model"],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": f"{prompt}\n\nReply with one JSON object that matches this JSON Schema:\n{json.dumps(schema)}"},
        ],
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {spec.get('api_key') or 'none'}"}
    if "openrouter.ai" in base:
        headers["X-Title"] = "PaperFold"
    ways = reasoning(base, level)
    key = (base, spec["model"], level)
    shapes = [(r, jm) for r in ways for jm in (True, False)]   # each reasoning shape with JSON mode, then without
    start = _WORKED.get(key, 0)
    last, busy = None, 0
    i = start
    while i < len(shapes):
        r, jm = shapes[i]
        try:
            d = _post(f"{base}/chat/completions", {**body, **r, **({"response_format": {"type": "json_object"}} if jm else {})}, headers, timeout)
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 502, 503, 529) and busy < len(WAITS):   # rate-limited or busy: wait, then the same again
                after = e.headers.get("Retry-After") if e.headers else None
                time.sleep(min(60, float(after)) if after and after.replace(".", "", 1).isdigit() else WAITS[busy])
                busy += 1
                continue
            if e.code in (400, 404, 415, 422) and i + 1 < len(shapes):   # this shape refused: the next one
                i += 1
                continue
            raise RuntimeError(f"{spec.get('provider') or base}: HTTP {e.code} {e.read()[:300].decode(errors='replace')}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"{spec.get('provider') or base}: {e.reason}")
        text = (d.get("choices") or [{}])[0].get("message", {}).get("content") or ""
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
        m = re.search(r"\{.*\}", text, re.S)
        if not m and i + 1 < len(shapes) and r:   # an answer left in the reasoning, none in the reply: ask the plain way
            i += 1
            continue
        if not m:
            raise RuntimeError("no JSON in reply")
        _WORKED[key] = i
        cost = ((d.get("usage") or {}).get("cost")) if "openrouter.ai" in base else None
        return json.loads(m.group(0)), cost
    raise RuntimeError(f"{spec.get('provider') or base}: {last}")
