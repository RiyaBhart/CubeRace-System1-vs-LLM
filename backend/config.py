"""The only model registry. No secret values are serialized to clients."""
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class ModelConfig(BaseModel):
    key: str
    name: str
    category: Literal['DECISION MODEL', 'LLM']
    id: str
    endpoint: Literal['decisions', 'chat']


MODELS = (
    ModelConfig(key='jev', name='Jev 1.13', category='DECISION MODEL', id='typesafe/jev-1.13', endpoint='decisions'),
    ModelConfig(key='luna', name='Luna Decisions', category='DECISION MODEL', id='openai/gpt-6-luna-decisions', endpoint='decisions'),
    ModelConfig(key='clef', name='Clef', category='DECISION MODEL', id='cloudflare/clef', endpoint='decisions'),
    ModelConfig(key='opus', name='Claude Opus 5.5', category='LLM', id='anthropic/claude-opus-5.5', endpoint='chat'),
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / '.env', extra='ignore')
    openrouter_api_key: SecretStr = SecretStr('')
    student_name: str = ''
    roll_number: str = ''
    mock_models: bool = False
    max_moves: int = Field(30, ge=1, le=30)
    game_timeout_s: float = Field(300, gt=0)
    request_timeout_s: float = Field(60, gt=0)
    recent_moves_n: int = Field(5, ge=0, le=30)
    history_length: int = Field(-1, ge=-1, le=30)  # -1 means complete history
    condition: Literal['pure', 'assisted'] = 'pure'
    max_retries: int = Field(0, ge=0, le=10)
    claude_reasoning_effort: Literal['low', 'medium', 'high', 'xhigh', 'max'] = 'low'
    claude_max_tokens: int = Field(512, ge=32, le=65536)
    live_request_limit: int = Field(604, ge=0)
    retry_backoff_s: float = Field(0.5, ge=0)
    invalid_consumes_attempt: bool = True
    bfs_depth: int = Field(5, ge=0, le=6)
    exact_max_depth: int = Field(8, ge=0, le=8)
    exact_node_budget: int = Field(2_000_000, ge=1)
    results_dir: Path = ROOT / 'results'
    http_referer: str = 'http://localhost:8000'
    x_title: str = 'Rubiks Cube Race - University Benchmark'
    use_kociemba: bool = False


settings = Settings()
