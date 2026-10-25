import logging
import httpx
from .adapters.chat_completions import ChatAdapter
from .adapters.decisions_api import DecisionsAdapter
from .adapters.mock import MockAdapter
from .config import Settings, ModelConfig
from .optimal import ExactSolver


def create_client(config: Settings) -> httpx.AsyncClient:
    return httpx.AsyncClient(http2=True, headers={
        'Authorization': f'Bearer {config.openrouter_api_key.get_secret_value()}',
        'HTTP-Referer': config.http_referer, 'X-Title': config.x_title},
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10, keepalive_expiry=600),
        timeout=config.request_timeout_s)


async def warmup(client: httpx.AsyncClient, config: Settings) -> None:
    if not config.mock_models:
        try:
            await client.get('https://openrouter.ai/api/v1/models', timeout=config.request_timeout_s)
        except httpx.RequestError:
            logging.getLogger(__name__).warning('Connection warmup failed; measured calls may include TLS setup')


def adapter_for(model: ModelConfig, client: httpx.AsyncClient, config: Settings, solver: ExactSolver, seed: int, permit=None):
    if config.mock_models:
        behavior = {'jev': 'random', 'luna': 'mixed', 'clef': 'invalid', 'opus': 'smart'}[model.key]
        return MockAdapter(behavior, seed, solver, config.max_retries)
    cls = DecisionsAdapter if model.endpoint == 'decisions' else ChatAdapter
    return cls(model, client, config, permit=permit)
