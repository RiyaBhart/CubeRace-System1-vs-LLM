from typing import Any, Literal
from pydantic import BaseModel, Field

Status = Literal['SOLVED', 'RAN_OUT_OF_MOVES', 'OUT_OF_TIME', 'ERROR', 'UNAVAILABLE',
                 'NOT_RUN', 'BUDGET_EXHAUSTED', 'SMOKE_TEST']


class AdapterResult(BaseModel):
    move: str | None = None
    latency_ms: float = 0  # sum of call+parse time, excludes backoff/queue
    latency_incl_retries_ms: float = 0
    raw_response: Any = None
    confidence: float | None = None
    tokens: int | None = None
    cost: float | None = None
    known_cost: float | None = None
    unknown_cost_requests: int = 0
    reasoning_tokens: int | None = None
    usage: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None
    retries_used: int = 0
    invalid_outputs: int = 0
    output_truncated: bool = False
    valid: bool = False
    unavailable: bool = False
    fatal: bool = False
    permanent: bool = False
    not_run: bool = False
    budget_exhausted: bool = False
    calls: list[dict[str, Any]] = Field(default_factory=list)


class MoveRecord(BaseModel):
    index: int
    move: str | None
    latency_ms: float
    latency_incl_retries_ms: float
    confidence: float | None
    valid: bool
    retries: int
    invalid_outputs: int
    state_before: str | None = None
    allowed_moves: list[str] = Field(default_factory=list)
    loop_filter_fallback: bool = False
    state_after: str
    timestamp: str
    elapsed_s: float
    response: AdapterResult


class GameResult(BaseModel):
    attempt_id: str
    run_id: str
    model: str
    model_id: str
    model_name: str
    category: str
    mock: bool
    diagnostic: bool = False
    condition: str = 'legacy'
    benchmark_set: str = 'legacy'
    agent_kind: Literal['model', 'baseline'] = 'model'
    action_policy: str = 'unrestricted'
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    puzzle_id: str
    repeat: int
    seed: int
    scramble: list[str]
    start_state: str
    status: Status = 'ERROR'
    moves_used: int = 0  # actually applied legal turns (used for optimality)
    attempts_used: int = 0  # includes wasted invalid turns when configured
    total_time_s: float = 0
    avg_latency_ms: float | None = None
    median_latency_ms: float | None = None
    p95_latency_ms: float | None = None
    avg_latency_incl_retries_ms: float | None = None
    invalid_count: int = 0
    retry_count: int = 0
    exact_optimal: int | None = None
    reference_moves: int | None = None
    reference_label: str | None = None
    optimality_gap: int | None = None
    tokens: int | None = None
    cost: float | None = None
    known_cost: float | None = None
    unknown_cost_requests: int = 0
    requests_used: int = 0
    reasoning_tokens: int | None = None
    error: str | None = None
    final_state: str = ''
    records: list[MoveRecord] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)
