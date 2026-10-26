"""One reliability policy for every real adapter; no response healing."""
import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any

import httpx

from ..config import ModelConfig, Settings
from ..cube_engine import NAMES, solved_state
from ..accounting import summarize_usage
from ..budget import BudgetExhausted, LivePermit
from ..schemas import AdapterResult

log = logging.getLogger(__name__)
from ..presentation import INSTRUCTIONS, shared_context


class IncompleteOutput(ValueError):
    """A provider explicitly exhausted the fixed output ceiling."""


class ModelAdapter(ABC):
    attempts_used: int | None = None  # runner supplies the consumed turn budget
    @abstractmethod
    async def get_move(self, state: str, recent_moves: list[str], allowed_moves: tuple[str, ...]) -> AdapterResult:
        raise NotImplementedError


class OpenRouterAdapter(ModelAdapter):
    def __init__(self, model: ModelConfig, client: httpx.AsyncClient, settings: Settings,
                 permit: LivePermit | None = None):
        self.model, self.client, self.settings = model, client, settings
        self.permit = permit
        self.semaphore = asyncio.Semaphore(1)

    @abstractmethod
    def request(self, state: str, recent: list[str], allowed: tuple[str, ...]) -> tuple[str, dict]:
        raise NotImplementedError

    @abstractmethod
    def parse(self, raw: dict, allowed: tuple[str, ...]) -> tuple[str, float | None]:
        raise NotImplementedError

    async def get_move(self, state: str, recent_moves: list[str], allowed_moves: tuple[str, ...]) -> AdapterResult:
        result = AdapterResult()
        self.partial_result = result  # allows deadline cancellation to retain completed calls and usage
        if self.settings.mock_models or self.permit is None:
            return AdapterResult(fatal=True, not_run=True, error='Live inference requires explicit per-run consent and budget')
        blocked = await asyncio.to_thread(self.permit.ledger.blocked, self.permit.run_id, self.model.key)
        if blocked:
            return AdapterResult(fatal=True, not_run=True, error=f'Model blocked for this run: {blocked}')
        async with self.semaphore:
            began = time.perf_counter()
            # One shared configurable retry budget for invalid outputs and
            # transient failures. Default zero. Permanent incompatibilities stop.
            for attempt in range(self.settings.max_retries+1):
                result.retries_used = attempt
                url, payload = self.request(state, recent_moves, allowed_moves)
                try:
                    request_id = await asyncio.to_thread(self.permit.reserve, self.model.key)
                except BudgetExhausted as exc:
                    result.error, result.fatal, result.budget_exhausted = str(exc), True, True
                    break
                tick = time.perf_counter()
                raw: Any = None
                retryable, backoff = False, False
                call: dict[str, Any] = {'attempt': attempt, 'request_id': request_id,
                                        'request_format': payload.get('response_format'), 'usage': None}
                try:
                    response = await self.client.post(url, json=payload, timeout=self.settings.request_timeout_s)
                    call['http_status'] = response.status_code
                    try:
                        raw = response.json()
                    except ValueError:
                        raw = {'unparsed_body': response.text[:10000]}
                    result.raw_response = raw
                    usage = raw.get('usage') if isinstance(raw, dict) else None
                    call['usage'] = usage if isinstance(usage, dict) else None
                    if isinstance(usage, dict):
                        result.usage.append(usage)
                    embedded = raw.get('error') if isinstance(raw, dict) else None
                    if response.is_error or embedded:
                        code = response.status_code if response.is_error else (embedded.get('code', 400) if isinstance(embedded, dict) else 400)
                        result.error = f'API error {code}'
                        metadata = embedded.get('metadata', {}) if isinstance(embedded, dict) else {}
                        if isinstance(metadata, dict) and metadata.get('scope') == 'key_limit':
                            # Do not echo key-management URLs, identifiers or raw credentials.
                            result.error = 'OpenRouter API key spending limit reached; further live calls are blocked by the provider'
                        lowered = json.dumps(raw).lower()
                        result.unavailable = code in (401, 403, 404) or 'model_not_found' in lowered or 'model-not-found' in lowered
                        if result.unavailable:
                            result.fatal = result.permanent = True
                        elif code == 429 or (isinstance(code, int) and code >= 500):
                            retryable = backoff = True
                        else:
                            result.fatal = result.permanent = True
                    else:
                        try:
                            move, confidence = self.parse(raw, allowed_moves)
                            if move not in allowed_moves:
                                raise ValueError('Move outside allowed set')
                            result.move, result.confidence, result.valid = move, confidence, True
                            result.error = None
                        except (ValueError, KeyError, TypeError, IndexError) as exc:
                            result.invalid_outputs += 1
                            result.error = f'Invalid output: {exc}'
                            result.output_truncated = isinstance(exc, IncompleteOutput)
                            retryable = not result.output_truncated
                except httpx.RequestError as exc:
                    result.error = f'Network error: {type(exc).__name__}'
                    retryable = backoff = True
                finally:
                    duration = (time.perf_counter()-tick)*1000
                    result.latency_ms += duration
                    call.update(latency_ms=duration, raw_response=raw, error=result.error)
                    result.calls.append(call)
                    billing = summarize_usage(result.calls)
                    for field in ('tokens', 'cost', 'reasoning_tokens', 'known_cost', 'unknown_cost_requests'):
                        setattr(result, field, billing[field])
                    await asyncio.to_thread(self.permit.ledger.finish, request_id, call['usage'])
                    if result.permanent:
                        await asyncio.to_thread(self.permit.ledger.block, self.permit.run_id, self.model.key, result.error)
                    # Only responses/metadata, never headers, request objects or the key.
                    log.info('model_call %s', json.dumps({'model': self.model.key, **call}, ensure_ascii=True))
                if result.valid or not retryable or attempt == self.settings.max_retries:
                    break
                if backoff:
                    await asyncio.sleep(self.settings.retry_backoff_s * 2**attempt)
            result.latency_incl_retries_ms = (time.perf_counter()-began)*1000
            result.retries_used = max(0, len(result.calls)-1)
        return result
