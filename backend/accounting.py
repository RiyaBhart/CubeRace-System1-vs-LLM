"""Normalize reported billing only. Unknown is never replaced with free usage."""
import math
from typing import Any


def numeric(value: Any) -> float | int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if math.isfinite(value) and value >= 0 else None


def normalize_usage(raw: Any) -> dict:
    usage = raw if isinstance(raw, dict) else {}
    prompt = numeric(usage.get('prompt_tokens', usage.get('input_tokens')))
    completion = numeric(usage.get('completion_tokens', usage.get('output_tokens')))
    details = usage.get('completion_tokens_details') or usage.get('output_tokens_details') or {}
    reasoning = numeric(details.get('reasoning_tokens')) if isinstance(details, dict) else None
    total = numeric(usage.get('total_tokens'))
    if total is None and prompt is not None and completion is not None:
        total = prompt + completion  # reasoning is already part of completion; never double count
    return {'prompt_tokens': prompt, 'completion_tokens': completion, 'reasoning_tokens': reasoning,
            'total_tokens': total, 'cost': numeric(usage.get('cost')), 'raw_usage': usage}


def summarize_usage(calls: list[dict]) -> dict:
    normalized = [normalize_usage(c.get('usage') or (c.get('raw_response') or {}).get('usage')
                                 if isinstance(c.get('raw_response') or {}, dict) else c.get('usage'))
                  for c in calls]
    costs = [n['cost'] for n in normalized if n['cost'] is not None]
    tokens = [n['total_tokens'] for n in normalized if n['total_tokens'] is not None]
    reasoning = [n['reasoning_tokens'] for n in normalized if n['reasoning_tokens'] is not None]
    return {'requests_used': len(calls), 'known_cost': sum(costs) if costs else None,
            'unknown_cost_requests': len(calls)-len(costs),
            'cost': sum(costs) if calls and len(costs) == len(calls) else None,
            'tokens': sum(tokens) if calls and len(tokens) == len(calls) else None,
            'reasoning_tokens': sum(reasoning) if calls and len(reasoning) == len(calls) else None}
